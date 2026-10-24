"""Virements entre deux comptes : deux jambes liées, créées, modifiées et annulées ensemble."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.entries import Entry
from finance.domain.ledger import cash_balance
from finance.domain.transfers import (
    TransferLegs,
    make_transfer,
)
from finance.domain.transfers import (
    update_transfer as update_legs,
)
from finance.domain.transfers import (
    void_transfer as void_legs,
)
from finance.services import loaders
from finance.services.errors import FieldError, NotFoundError, ValidationFailed
from finance.services.transactions import TransactionOutcome, copy_version


@dataclass(frozen=True)
class TransferData:
    from_account_id: str
    to_account_id: str
    trade_date: date
    amount: Decimal
    currency: str
    label: str | None = None


@dataclass(frozen=True)
class TransferOutcome:
    group_id: str
    out: TransactionOutcome
    into: TransactionOutcome


def _account(session: Session, account_id: str, field: str) -> models.Account:
    account = session.get(models.Account, account_id)
    if account is None:
        raise ValidationFailed.single(field, "Compte introuvable.")
    return account


def _check_dates_and_currency(
    source: models.Account, target: models.Account, trade_date: date, currency: str
) -> None:
    problems: list[FieldError] = []
    if currency != source.currency or currency != target.currency:
        problems.append(
            FieldError("currency", "La devise du virement doit être celle des deux comptes.")
        )
    if trade_date < source.opened_on or trade_date < target.opened_on:
        problems.append(
            FieldError("trade_date", "La date du virement précède l'ouverture d'un des comptes.")
        )
    if problems:
        raise ValidationFailed(problems)


def _warnings(session: Session, source: models.Account, leg: Entry) -> list[str]:
    entries = loaders.load_entries(session, account_ids=[source.id])
    others = [e for e in entries if e.transaction_id != leg.transaction_id]
    if cash_balance(others, account_id=source.id, as_of=leg.trade_date) + leg.cash_amount < 0:
        return ["Les liquidités du compte sont négatives à cette date."]
    return []


def create_transfer(session: Session, data: TransferData) -> TransferOutcome:
    source = _account(session, data.from_account_id, "from_account_id")
    target = _account(session, data.to_account_id, "to_account_id")
    if source.id == target.id:
        raise ValidationFailed.single("to_account_id", "Un virement relie deux comptes différents.")
    if data.amount <= 0:
        raise ValidationFailed.single("amount", "Le montant doit être strictement positif.")
    _check_dates_and_currency(source, target, data.trade_date, data.currency)

    group = models.TransferGroup()
    session.add(group)
    session.flush()
    legs = make_transfer(
        group_id=group.id,
        out_transaction_id=str(uuid.uuid4()),
        in_transaction_id=str(uuid.uuid4()),
        from_account=source.id,
        to_account=target.id,
        amount=data.amount,
        trade_date=data.trade_date,
        currency=data.currency,
        created_at=datetime.now(UTC),
        label=data.label,
    )
    rows: list[models.TransactionVersion] = []
    for leg in (legs.out, legs.into):
        session.add(models.Transaction(id=leg.transaction_id, account_id=leg.account_id))
        session.flush()
        row = models.TransactionVersion(
            transaction_id=leg.transaction_id,
            version=1,
            voided=False,
            type=leg.type,
            trade_date=leg.trade_date,
            fees=Decimal(0),
            cash_amount=leg.cash_amount,
            currency=leg.currency,
            transfer_group_id=group.id,
            label=leg.label,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return TransferOutcome(
        group_id=group.id,
        out=TransactionOutcome(version=rows[0], warnings=_warnings(session, source, legs.out)),
        into=TransactionOutcome(version=rows[1], warnings=[]),
    )


def _current_legs(
    session: Session, group_id: str
) -> tuple[models.TransactionVersion, models.TransactionVersion]:
    statement = loaders.latest_versions_statement().where(
        models.TransactionVersion.transfer_group_id == group_id
    )
    rows = list(session.scalars(statement).unique())
    outs = [r for r in rows if r.cash_amount < 0]
    ins = [r for r in rows if r.cash_amount > 0]
    if len(rows) != 2 or len(outs) != 1 or len(ins) != 1:
        raise NotFoundError("Virement", group_id)
    return outs[0], ins[0]


def _legs_from_rows(
    out: models.TransactionVersion, into: models.TransactionVersion
) -> TransferLegs:
    return TransferLegs(out=loaders.entry_from_row(out), into=loaders.entry_from_row(into))


def update_transfer(
    session: Session,
    group_id: str,
    *,
    amount: Decimal | None = None,
    trade_date: date | None = None,
    label: str | None = None,
) -> TransferOutcome:
    """Modifie les deux jambes ensemble ; chacune reçoit une nouvelle version."""
    out_row, in_row = _current_legs(session, group_id)
    source = _account(session, out_row.account_id, "from_account_id")
    target = _account(session, in_row.account_id, "to_account_id")
    try:
        updated = update_legs(
            _legs_from_rows(out_row, in_row), amount=amount, trade_date=trade_date, label=label
        )
    except ValueError as error:
        raise ValidationFailed.single("amount", str(error)) from error
    _check_dates_and_currency(source, target, updated.out.trade_date, updated.out.currency)
    changes = {
        "trade_date": updated.out.trade_date,
        "label": updated.out.label,
        "voided": False,
    }
    new_out = copy_version(session, out_row, cash_amount=updated.out.cash_amount, **changes)
    new_in = copy_version(session, in_row, cash_amount=updated.into.cash_amount, **changes)
    return TransferOutcome(
        group_id=group_id,
        out=TransactionOutcome(version=new_out, warnings=_warnings(session, source, updated.out)),
        into=TransactionOutcome(version=new_in, warnings=[]),
    )


def void_transfer(session: Session, group_id: str) -> TransferOutcome:
    """Annule les deux jambes ensemble ; sans effet sur une jambe déjà annulée."""
    out_row, in_row = _current_legs(session, group_id)
    if out_row.voided and in_row.voided:
        return TransferOutcome(
            group_id=group_id,
            out=TransactionOutcome(version=out_row, warnings=[]),
            into=TransactionOutcome(version=in_row, warnings=[]),
        )
    void_legs(_legs_from_rows(out_row, in_row))  # vérifie l'invariant avant d'écrire
    return TransferOutcome(
        group_id=group_id,
        out=TransactionOutcome(
            version=out_row if out_row.voided else copy_version(session, out_row, voided=True),
            warnings=[],
        ),
        into=TransactionOutcome(
            version=in_row if in_row.voided else copy_version(session, in_row, voided=True),
            warnings=[],
        ),
    )


__all__ = ["TransferData", "TransferOutcome", "create_transfer", "update_transfer", "void_transfer"]
_ = sa  # sqlalchemy reste importé pour les requêtes futures de ce module
