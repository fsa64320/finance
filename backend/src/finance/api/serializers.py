"""Transformation des objets de la base et des services en JSON conforme au contrat.

Les dictionnaires ne contiennent que les champs à émettre : un champ optionnel absent est omis,
un champ nullable du contrat est émis à `null`. Les décimaux sortent en chaînes canoniques.
"""

from decimal import Decimal
from typing import Any

from finance.db import models
from finance.db.types import canonical_decimal_text
from finance.domain.valuation import PositionValue, ValuationWarning
from finance.services.accounts import AccountOverview
from finance.services.balances import BalanceData
from finance.services.dashboard import AllocationResult, SeriesResult, Summary
from finance.services.transactions import TransactionOutcome
from finance.services.transfers import TransferOutcome


def dec(value: Decimal) -> str:
    return canonical_decimal_text(value)


def account(row: models.Account) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": row.id,
        "type": row.type.value,
        "name": row.name,
        "currency": row.currency,
        "opened_on": row.opened_on.isoformat(),
        "closed_on": None if row.closed_on is None else row.closed_on.isoformat(),
        "settings": row.settings,
    }
    if row.institution is not None:
        body["institution"] = row.institution
    return body


def account_summary(overview: AccountOverview) -> dict[str, Any]:
    return {
        **account(overview.account),
        "value": dec(overview.value.total),
        "estimated": overview.value.estimated,
    }


def _position(position: PositionValue) -> dict[str, Any]:
    body: dict[str, Any] = {
        "instrument_id": position.instrument_id,
        "kind": position.kind.value,
        "quantity": dec(position.quantity),
        "total_cost": dec(position.total_cost),
        "unit_cost": None if position.unit_cost is None else dec(position.unit_cost),
        "value": None if position.value is None else dec(position.value),
        "price": None if position.price is None else dec(position.price),
        "price_date": None if position.price_date is None else position.price_date.isoformat(),
        "estimated": position.estimated,
    }
    return body


def _warning(warning: ValuationWarning) -> dict[str, Any]:
    return {
        "code": warning.code,
        "instrument_id": warning.instrument_id,
        "message": warning.message,
    }


def account_detail(overview: AccountOverview) -> dict[str, Any]:
    body = account_summary(overview)
    body["cash"] = dec(overview.cash)
    body["positions"] = [_position(p) for p in overview.value.positions]
    body["warnings"] = [_warning(w) for w in overview.value.warnings]
    usage = overview.deposit_cap_usage
    if usage is not None:
        body["deposit_cap_usage"] = {
            "deposited": dec(usage.used),
            "cap": dec(usage.cap),
            "remaining": dec(usage.remaining),
            "exceeded": usage.exceeded,
        }
    if overview.locked_amount is not None:
        body["locked_amount"] = dec(overview.locked_amount)
    return body


def instrument(row: models.Instrument) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": row.id,
        "kind": row.kind.value,
        "name": row.name,
        "currency": row.currency,
        "price_mode": row.price_mode.value,
    }
    if row.isin is not None:
        body["isin"] = row.isin
    if row.price_ticker is not None:
        body["price_ticker"] = row.price_ticker
    return body


def transaction(row: models.TransactionVersion) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": row.transaction_id,
        "version": row.version,
        "voided": row.voided,
        "account_id": row.account_id,
        "type": row.type.value,
        "trade_date": row.trade_date.isoformat(),
        "instrument_id": row.instrument_id,
        "fees": dec(row.fees),
        "cash_amount": dec(row.cash_amount),
        "currency": row.currency,
        "unlock_date": None if row.unlock_date is None else row.unlock_date.isoformat(),
        "transfer_group_id": row.transfer_group_id,
        "import_id": row.import_id,
        "created_at": row.created_at.isoformat(),
    }
    if row.quantity is not None:
        body["quantity"] = dec(row.quantity)
    if row.unit_price is not None:
        body["unit_price"] = dec(row.unit_price)
    if row.label is not None:
        body["label"] = row.label
    return body


def transaction_result(outcome: TransactionOutcome) -> dict[str, Any]:
    return {"transaction": transaction(outcome.version), "warnings": outcome.warnings}


def transfer_result(outcome: TransferOutcome) -> dict[str, Any]:
    return {
        "transfer_group_id": outcome.group_id,
        "out": transaction_result(outcome.out),
        "in": transaction_result(outcome.into),
    }


def declared_balance(row: models.DeclaredBalance) -> dict[str, Any]:
    data = BalanceData(
        account_id=row.account_id,
        instrument_id=row.instrument_id,
        balance_date=row.balance_date,
        amount=row.amount,
        currency=row.currency,
    )
    return {
        "account_id": data.account_id,
        "instrument_id": data.instrument_id,
        "balance_date": data.balance_date.isoformat(),
        "amount": dec(data.amount),
        "currency": data.currency,
    }


def dashboard_summary(result: Summary) -> dict[str, Any]:
    return {
        "currency": result.currency,
        "net_worth": dec(result.net_worth),
        "excludes_debts": result.excludes_debts,
        "estimated": result.estimated,
        "as_of": result.as_of.isoformat(),
        "notices": [
            {
                "kind": notice.kind,
                "message": notice.message,
                "instrument_id": notice.instrument_id,
                "account_id": notice.account_id,
            }
            for notice in result.notices
        ],
    }


def dashboard_series(result: SeriesResult) -> dict[str, Any]:
    return {
        "currency": result.currency,
        "points": [
            {"date": p.date.isoformat(), "value": dec(p.value), "estimated": p.estimated}
            for p in result.points
        ],
    }


def dashboard_allocation(result: AllocationResult) -> dict[str, Any]:
    return {
        "currency": result.currency,
        "slices": [
            {
                "asset_class": s.asset_class.value,
                "value": dec(s.value),
                "weight_percent": dec(s.weight_percent),
            }
            for s in result.slices
        ],
    }
