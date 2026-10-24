"""Opérations versionnées : saisie, modification, annulation, historique et liste (FR-003, FR-004).

Une opération a une ligne `transaction` (identité) et une ligne `transaction_version` par version.
Aucune ligne n'est jamais modifiée ni supprimée (principe II) : toute correction ajoute une version.
"""

import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import TransactionType as T
from finance.domain.ledger import cash_balance, cash_effect, positions
from finance.domain.rules import check_transaction
from finance.services import loaders
from finance.services.errors import FieldError, NotFoundError, ValidationFailed

if TYPE_CHECKING:
    pass

_TRANSFER_TYPES = frozenset({T.TRANSFER_OUT, T.TRANSFER_IN})
_CURRENCY = re.compile(r"[A-Z]{3}")


@dataclass(frozen=True)
class TransactionData:
    account_id: str
    type: T
    trade_date: date
    currency: str
    instrument_id: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    fees: Decimal = Decimal(0)
    unlock_date: date | None = None
    label: str | None = None


@dataclass(frozen=True)
class TransactionOutcome:
    version: models.TransactionVersion
    warnings: list[str]


@dataclass(frozen=True)
class Page:
    items: list[models.TransactionVersion]
    next_cursor: str | None


def _account(session: Session, account_id: str) -> models.Account:
    account = session.get(models.Account, account_id)
    if account is None:
        raise ValidationFailed.single("account_id", "Compte introuvable.")
    return account


def _latest_row(session: Session, transaction_id: str) -> models.TransactionVersion:
    statement = (
        sa.select(models.TransactionVersion)
        .where(models.TransactionVersion.transaction_id == transaction_id)
        .order_by(models.TransactionVersion.version.desc())
        .limit(1)
    )
    row = session.scalars(statement).first()
    if row is None:
        raise NotFoundError("Opération", transaction_id)
    return row


def _prepare(
    session: Session, data: TransactionData, *, replacing: str | None = None
) -> tuple[Decimal, list[str]]:
    """Valide l'opération et calcule son effet de trésorerie ; renvoie aussi les avertissements."""
    account = _account(session, data.account_id)
    if (
        data.instrument_id is not None
        and session.get(models.Instrument, data.instrument_id) is None
    ):
        raise ValidationFailed.single("instrument_id", "Actif introuvable.")
    if not _CURRENCY.fullmatch(data.currency):
        raise ValidationFailed.single(
            "currency", "La devise est un code de trois lettres majuscules."
        )
    if data.currency != account.currency:
        raise ValidationFailed.single(
            "currency",
            f"L'opération doit être en {account.currency}, la devise du compte "
            "(la conversion de devises arrive plus tard).",
        )

    others = [
        entry
        for entry in loaders.load_entries(session, account_ids=[account.id])
        if entry.transaction_id != replacing
    ]
    held: Decimal | None = None
    if data.type is T.SELL and data.instrument_id is not None:
        held = positions(others, as_of=data.trade_date, account_id=account.id).get(
            (account.id, data.instrument_id), Decimal(0)
        )

    result = check_transaction(
        account_type=account.type,
        account_opened_on=account.opened_on,
        type=data.type,
        trade_date=data.trade_date,
        amount=data.amount,
        has_instrument=data.instrument_id is not None,
        quantity=data.quantity,
        unit_price=data.unit_price,
        fees=data.fees,
        unlock_date=data.unlock_date,
        held_quantity=held,
    )
    if not result.ok:
        raise ValidationFailed([FieldError(v.field, v.message) for v in result.errors])
    try:
        cash = cash_effect(
            data.type,
            amount=data.amount,
            quantity=data.quantity,
            unit_price=data.unit_price,
            fees=data.fees,
        )
    except ValueError as error:
        raise ValidationFailed.single("amount", str(error)) from error

    warnings = [warning.message for warning in result.warnings]
    if cash_balance(others, account_id=account.id, as_of=data.trade_date) + cash < 0:
        warnings.append("Les liquidités du compte sont négatives à cette date.")
    return cash, warnings


def _add_version(
    session: Session,
    transaction_id: str,
    version: int,
    *,
    data: TransactionData,
    cash_amount: Decimal,
    voided: bool = False,
    transfer_group_id: str | None = None,
    import_id: str | None = None,
) -> models.TransactionVersion:
    row = models.TransactionVersion(
        transaction_id=transaction_id,
        version=version,
        voided=voided,
        type=data.type,
        trade_date=data.trade_date,
        instrument_id=data.instrument_id,
        quantity=data.quantity,
        unit_price=data.unit_price,
        fees=data.fees,
        cash_amount=cash_amount,
        currency=data.currency,
        unlock_date=data.unlock_date,
        transfer_group_id=transfer_group_id,
        label=data.label,
        import_id=import_id,
    )
    session.add(row)
    session.flush()
    return row


def copy_version(
    session: Session, previous: models.TransactionVersion, **changes: Any
) -> models.TransactionVersion:
    """Ajoute la version suivante de `previous` avec `changes`, sans modifier `previous`."""
    values: dict[str, Any] = {
        "transaction_id": previous.transaction_id,
        "version": previous.version + 1,
        "voided": previous.voided,
        "type": previous.type,
        "trade_date": previous.trade_date,
        "instrument_id": previous.instrument_id,
        "quantity": previous.quantity,
        "unit_price": previous.unit_price,
        "fees": previous.fees,
        "cash_amount": previous.cash_amount,
        "currency": previous.currency,
        "unlock_date": previous.unlock_date,
        "transfer_group_id": previous.transfer_group_id,
        "label": previous.label,
        "import_id": previous.import_id,
    }
    values.update(changes)
    row = models.TransactionVersion(**values)
    session.add(row)
    session.flush()
    return row


def create_transaction(session: Session, data: TransactionData) -> TransactionOutcome:
    cash, warnings = _prepare(session, data)
    transaction = models.Transaction(account_id=data.account_id)
    session.add(transaction)
    session.flush()
    row = _add_version(session, transaction.id, 1, data=data, cash_amount=cash)
    return TransactionOutcome(version=row, warnings=warnings)


def update_transaction(
    session: Session, transaction_id: str, data: TransactionData
) -> TransactionOutcome:
    previous = _latest_row(session, transaction_id)
    if previous.transfer_group_id is not None or data.type in _TRANSFER_TYPES:
        raise ValidationFailed.single(
            "id", "Un virement se modifie par ses deux jambes à la fois, pas séparément."
        )
    if data.account_id != previous.account_id:
        raise ValidationFailed.single(
            "account_id",
            "Une opération ne change pas de compte : annulez-la, puis saisissez-en une autre.",
        )
    cash, warnings = _prepare(session, data, replacing=transaction_id)
    row = _add_version(
        session,
        transaction_id,
        previous.version + 1,
        data=data,
        cash_amount=cash,
        import_id=previous.import_id,
    )
    return TransactionOutcome(version=row, warnings=warnings)


def void_transaction(session: Session, transaction_id: str) -> TransactionOutcome:
    """Annule l'opération (un virement, avec ses deux jambes) ; sans effet si déjà annulée."""
    previous = _latest_row(session, transaction_id)
    if previous.transfer_group_id is not None:
        from finance.services import transfers

        group = transfers.void_transfer(session, previous.transfer_group_id)
        leg = group.out if group.out.version.transaction_id == transaction_id else group.into
        return leg
    if previous.voided:
        return TransactionOutcome(version=previous, warnings=[])
    return TransactionOutcome(version=copy_version(session, previous, voided=True), warnings=[])


def get_transaction(
    session: Session, transaction_id: str
) -> tuple[models.TransactionVersion, list[models.TransactionVersion]]:
    """Version courante et historique complet (de la plus ancienne à la plus récente)."""
    if session.get(models.Transaction, transaction_id) is None:
        raise NotFoundError("Opération", transaction_id)
    versions = list(
        session.scalars(
            sa.select(models.TransactionVersion)
            .where(models.TransactionVersion.transaction_id == transaction_id)
            .order_by(models.TransactionVersion.version)
        )
    )
    return versions[-1], versions


def _encode_cursor(row: models.TransactionVersion) -> str:
    created = row.transaction.created_at.isoformat()
    payload = {"d": row.trade_date.isoformat(), "c": created, "i": row.transaction_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[date, datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return (
            date.fromisoformat(payload["d"]),
            datetime.fromisoformat(payload["c"]),
            str(payload["i"]),
        )
    except (binascii.Error, ValueError, KeyError, TypeError):
        raise ValidationFailed.single("cursor", "Curseur de pagination invalide.") from None


def list_transactions(
    session: Session,
    *,
    account_id: str | None = None,
    instrument_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_voided: bool = False,
    limit: int = 100,
    cursor: str | None = None,
) -> Page:
    """Opérations courantes, de la plus récente à la plus ancienne, avec pagination par curseur."""
    version, txn = models.TransactionVersion, models.Transaction
    statement = loaders.latest_versions_statement().join(txn, txn.id == version.transaction_id)
    if account_id is not None:
        statement = statement.where(txn.account_id == account_id)
    if instrument_id is not None:
        statement = statement.where(version.instrument_id == instrument_id)
    if date_from is not None:
        statement = statement.where(version.trade_date >= date_from)
    if date_to is not None:
        statement = statement.where(version.trade_date <= date_to)
    if not include_voided:
        statement = statement.where(version.voided.is_(False))
    if cursor is not None:
        last_date, last_created, last_id = _decode_cursor(cursor)
        statement = statement.where(
            sa.or_(
                version.trade_date < last_date,
                sa.and_(version.trade_date == last_date, txn.created_at < last_created),
                sa.and_(
                    version.trade_date == last_date,
                    txn.created_at == last_created,
                    txn.id < last_id,
                ),
            )
        )
    statement = statement.order_by(
        version.trade_date.desc(), txn.created_at.desc(), txn.id.desc()
    ).limit(limit + 1)
    rows = list(session.scalars(statement).unique())
    page = rows[:limit]
    return Page(items=page, next_cursor=_encode_cursor(page[-1]) if len(rows) > limit else None)
