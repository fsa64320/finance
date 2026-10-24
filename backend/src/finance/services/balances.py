"""Soldes déclarés des actifs sans cours : fonds en euros, trésorerie (FR-006)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import InstrumentKind
from finance.services.errors import FieldError, ValidationFailed

_WITHOUT_PRICE = frozenset({InstrumentKind.EURO_FUND, InstrumentKind.CASH})


@dataclass(frozen=True)
class BalanceData:
    account_id: str
    instrument_id: str
    balance_date: date
    amount: Decimal
    currency: str


def declare_balance(session: Session, data: BalanceData) -> models.DeclaredBalance:
    """Ajoute un solde déclaré ; une correction est une nouvelle ligne, la plus récente fait foi."""
    problems: list[FieldError] = []
    account = session.get(models.Account, data.account_id)
    instrument = session.get(models.Instrument, data.instrument_id)
    if account is None:
        problems.append(FieldError("account_id", "Compte introuvable."))
    if instrument is None:
        problems.append(FieldError("instrument_id", "Actif introuvable."))
    elif instrument.kind not in _WITHOUT_PRICE:
        problems.append(
            FieldError(
                "instrument_id", "Seuls un fonds en euros ou la trésorerie ont un solde déclaré."
            )
        )
    if data.amount < 0:
        problems.append(FieldError("amount", "Le solde ne peut pas être négatif."))
    if account is not None and data.currency != account.currency:
        problems.append(FieldError("currency", "La devise du solde doit être celle du compte."))
    if problems:
        raise ValidationFailed(problems)
    row = models.DeclaredBalance(
        account_id=data.account_id,
        instrument_id=data.instrument_id,
        balance_date=data.balance_date,
        amount=data.amount,
        currency=data.currency,
    )
    session.add(row)
    session.flush()
    return row
