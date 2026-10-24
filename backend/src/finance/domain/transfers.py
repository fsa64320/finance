"""Virements entre deux comptes de l'utilisateur : deux jambes liées, neutres pour le patrimoine."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from finance.domain.entries import Entry, new_version, void
from finance.domain.enums import TransactionType as T


@dataclass(frozen=True)
class TransferLegs:
    out: Entry  # jambe de sortie, sur le compte source
    into: Entry  # jambe d'entrée, sur le compte destination


def make_transfer(
    *,
    group_id: str,
    out_transaction_id: str,
    in_transaction_id: str,
    from_account: str,
    to_account: str,
    amount: Decimal,
    trade_date: date,
    currency: str,
    created_at: datetime,
    label: str | None = None,
) -> TransferLegs:
    if from_account == to_account:
        raise ValueError("Un virement relie deux comptes différents.")
    if amount <= 0:
        raise ValueError("Le montant d'un virement doit être strictement positif.")
    common = {
        "version": 1,
        "trade_date": trade_date,
        "currency": currency,
        "created_at": created_at,
        "transfer_group_id": group_id,
        "label": label,
    }
    legs = TransferLegs(
        out=Entry(
            transaction_id=out_transaction_id,
            account_id=from_account,
            type=T.TRANSFER_OUT,
            cash_amount=-amount,
            **common,  # type: ignore[arg-type]
        ),
        into=Entry(
            transaction_id=in_transaction_id,
            account_id=to_account,
            type=T.TRANSFER_IN,
            cash_amount=amount,
            **common,  # type: ignore[arg-type]
        ),
    )
    validate_transfer(legs.out, legs.into)
    return legs


def validate_transfer(out: Entry, into: Entry) -> None:
    """Même montant, même date, même devise et deux comptes différents pour les deux jambes."""
    if out.type is not T.TRANSFER_OUT or into.type is not T.TRANSFER_IN:
        raise ValueError("Les types des jambes doivent être sortie puis entrée.")
    if out.transfer_group_id is None or out.transfer_group_id != into.transfer_group_id:
        raise ValueError("Les deux jambes doivent partager le même groupe.")
    if out.account_id == into.account_id:
        raise ValueError("Les deux jambes doivent viser deux comptes différents.")
    if out.cash_amount != -into.cash_amount or into.cash_amount <= 0:
        raise ValueError("Les deux jambes doivent avoir le même montant, positif.")
    if out.trade_date != into.trade_date:
        raise ValueError("Les deux jambes doivent avoir la même date.")
    if out.currency != into.currency:
        raise ValueError("Les deux jambes doivent avoir la même devise.")


def update_transfer(
    legs: TransferLegs,
    *,
    amount: Decimal | None = None,
    trade_date: date | None = None,
    label: str | None = None,
) -> TransferLegs:
    """Modifie les deux jambes ensemble ; chacune reçoit une nouvelle version."""
    new_amount = legs.into.cash_amount if amount is None else amount
    if new_amount <= 0:
        raise ValueError("Le montant d'un virement doit être strictement positif.")
    new_date = legs.into.trade_date if trade_date is None else trade_date
    new_label = legs.into.label if label is None else label
    updated = TransferLegs(
        out=new_version(legs.out, cash_amount=-new_amount, trade_date=new_date, label=new_label),
        into=new_version(legs.into, cash_amount=new_amount, trade_date=new_date, label=new_label),
    )
    validate_transfer(updated.out, updated.into)
    return updated


def void_transfer(legs: TransferLegs) -> TransferLegs:
    """Annule les deux jambes ensemble."""
    return TransferLegs(out=void(legs.out), into=void(legs.into))
