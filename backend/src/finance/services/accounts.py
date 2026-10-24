"""Comptes : création, modification, clôture et vue valorisée (FR-001, FR-005 à FR-008)."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.db import models
from finance.db.types import canonical_decimal_text
from finance.domain.caps import (
    DEFAULT_LIVRET_A_CAP,
    DEFAULT_PEA_CAP,
    CapStatus,
    cap_status,
    deposits_total,
    lock_status,
)
from finance.domain.enums import AccountType
from finance.domain.livret_a import LivretASchedule
from finance.domain.valuation import AccountValue, value_account
from finance.services import loaders
from finance.services.errors import ConflictError, NotFoundError, ValidationFailed

REFERENCE_CURRENCY = "EUR"
DEFAULT_LOCK_YEARS = 5
_CURRENCY = re.compile(r"[A-Z]{3}")


def default_settings(kind: AccountType) -> dict[str, Any]:
    if kind is AccountType.PEA:
        return {"deposit_cap": canonical_decimal_text(DEFAULT_PEA_CAP)}
    if kind is AccountType.LIVRET_A:
        return {"deposit_cap": canonical_decimal_text(DEFAULT_LIVRET_A_CAP)}
    if kind is AccountType.PEE:
        return {"lock_years": DEFAULT_LOCK_YEARS}
    return {}


def _checked_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    checked = dict(settings)
    if "deposit_cap" in checked:
        raw = checked["deposit_cap"]
        try:
            if not isinstance(raw, str):
                raise ValueError
            cap = Decimal(canonical_decimal_text(raw))
            if cap <= 0:
                raise ValueError
        except (ValueError, TypeError):
            raise ValidationFailed.single(
                "settings.deposit_cap", "Le plafond est un décimal strictement positif (texte)."
            ) from None
        checked["deposit_cap"] = canonical_decimal_text(cap)
    if "lock_years" in checked:
        years = checked["lock_years"]
        if isinstance(years, bool) or not isinstance(years, int) or years <= 0:
            raise ValidationFailed.single(
                "settings.lock_years", "La durée de blocage est un nombre d'années entier positif."
            )
    return checked


def _ensure_name_is_free(session: Session, name: str, *, except_id: str | None = None) -> None:
    statement = sa.select(models.Account.id).where(
        models.Account.name == name, models.Account.closed_on.is_(None)
    )
    if except_id is not None:
        statement = statement.where(models.Account.id != except_id)
    if session.scalar(statement) is not None:
        raise ConflictError(f"Un compte ouvert porte déjà le nom « {name} ».")


def create_account(
    session: Session,
    *,
    type: AccountType,
    name: str,
    opened_on: date,
    institution: str | None = None,
    currency: str | None = None,
    settings: Mapping[str, Any] | None = None,
) -> models.Account:
    name = name.strip()
    if not name:
        raise ValidationFailed.single("name", "Le nom du compte est obligatoire.")
    code = currency or REFERENCE_CURRENCY
    if not _CURRENCY.fullmatch(code):
        raise ValidationFailed.single(
            "currency", "La devise est un code de trois lettres majuscules."
        )
    merged = {**default_settings(type), **_checked_settings(settings or {})}
    _ensure_name_is_free(session, name)
    account = models.Account(
        type=type,
        name=name,
        institution=institution,
        currency=code,
        opened_on=opened_on,
        settings=merged,
    )
    session.add(account)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(f"Un compte ouvert porte déjà le nom « {name} ».") from error
    return account


def get_account(session: Session, account_id: str) -> models.Account:
    account = session.get(models.Account, account_id)
    if account is None:
        raise NotFoundError("Compte", account_id)
    return account


def list_accounts(session: Session, *, include_closed: bool = False) -> list[models.Account]:
    statement = sa.select(models.Account).order_by(models.Account.opened_on, models.Account.name)
    if not include_closed:
        statement = statement.where(models.Account.closed_on.is_(None))
    return list(session.scalars(statement))


def update_account(session: Session, account_id: str, changes: Mapping[str, Any]) -> models.Account:
    """Applique les champs fournis ; `closed_on: None` rouvre le compte."""
    account = get_account(session, account_id)
    name = account.name
    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise ValidationFailed.single("name", "Le nom du compte est obligatoire.")
    closed_on = account.closed_on
    if "closed_on" in changes:
        closed_on = changes["closed_on"]
        if closed_on is not None and closed_on < account.opened_on:
            raise ValidationFailed.single(
                "closed_on", "La date de clôture ne peut pas précéder l'ouverture."
            )
    settings = account.settings
    if "settings" in changes:
        settings = {**account.settings, **_checked_settings(changes["settings"] or {})}
    if closed_on is None:
        _ensure_name_is_free(session, name, except_id=account.id)  # avant toute écriture

    account.name = name
    account.closed_on = closed_on
    account.settings = settings
    if "institution" in changes:
        account.institution = changes["institution"]
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Un compte ouvert porte déjà ce nom.") from error
    return account


@dataclass(frozen=True)
class AccountOverview:
    account: models.Account
    as_of: date
    value: AccountValue
    deposit_cap_usage: CapStatus | None  # PEA : versements ; Livret A : solde
    locked_amount: Decimal | None  # PEE : sommes encore bloquées

    @property
    def cash(self) -> Decimal:
        return self.value.cash


def _cap(account: models.Account, default: Decimal) -> Decimal:
    raw = account.settings.get("deposit_cap")
    return default if raw is None else Decimal(str(raw))


def account_overviews(
    session: Session, accounts: Sequence[models.Account], as_of: date
) -> list[AccountOverview]:
    """Vue valorisée de plusieurs comptes ; les données communes sont lues une seule fois."""
    entries = loaders.load_entries(session, account_ids=[a.id for a in accounts])
    infos = loaders.load_instrument_infos(session)
    prices = loaders.load_prices(session)
    balances = loaders.load_declared_balances(session)
    fx = loaders.load_fx_table(session)
    livret_rates = loaders.load_livret_rates(session)
    overviews: list[AccountOverview] = []
    for account in accounts:
        schedule = (
            LivretASchedule.from_entries(entries, account.id, livret_rates, until=as_of)
            if account.type is AccountType.LIVRET_A
            else None
        )
        value = value_account(
            account_id=account.id,
            entries=entries,
            instruments=infos,
            prices=prices,
            balances=balances,
            as_of=as_of,
            currency=account.currency,
            fx=fx,
            livret=schedule,
        )
        usage: CapStatus | None = None
        locked: Decimal | None = None
        if account.type is AccountType.PEA:
            used = deposits_total(entries, account_id=account.id, as_of=as_of)
            usage = cap_status(used, _cap(account, DEFAULT_PEA_CAP))
        elif account.type is AccountType.LIVRET_A:
            usage = cap_status(value.cash, _cap(account, DEFAULT_LIVRET_A_CAP))
        elif account.type is AccountType.PEE:
            locked = lock_status(entries, account_id=account.id, as_of=as_of).locked
        overviews.append(
            AccountOverview(
                account=account,
                as_of=as_of,
                value=value,
                deposit_cap_usage=usage,
                locked_amount=locked,
            )
        )
    return overviews


def account_overview(session: Session, account: models.Account, as_of: date) -> AccountOverview:
    return account_overviews(session, [account], as_of)[0]
