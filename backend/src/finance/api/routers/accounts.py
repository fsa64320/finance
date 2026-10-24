"""Routes des comptes (contrat : tag `accounts`)."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.schemas import AccountInput, AccountPatch, DeclaredBalanceInput
from finance.services import accounts, balances

router = APIRouter(tags=["accounts"])

NOT_FOUND = {"description": "Compte introuvable"}
CONFLICT = {"description": "Un compte ouvert porte déjà ce nom"}


@router.get("/accounts")
def list_accounts(
    include_closed: bool = False,
    as_of: date | None = None,
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    rows = accounts.list_accounts(session, include_closed=include_closed)
    overviews = accounts.account_overviews(session, rows, as_of or date.today())
    return [serializers.account_summary(overview) for overview in overviews]


@router.post("/accounts", status_code=201, responses={409: CONFLICT})
def create_account(
    body: AccountInput, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    row = accounts.create_account(
        session,
        type=body.type,
        name=body.name,
        opened_on=body.opened_on,
        institution=body.institution,
        currency=body.currency,
        settings=body.settings,
    )
    return serializers.account(row)


@router.get("/accounts/{accountId}", responses={404: NOT_FOUND})
def get_account(
    accountId: UUID,
    as_of: date | None = None,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    row = accounts.get_account(session, str(accountId))
    return serializers.account_detail(
        accounts.account_overview(session, row, as_of or date.today())
    )


@router.patch("/accounts/{accountId}", responses={404: NOT_FOUND, 409: CONFLICT})
def patch_account(
    accountId: UUID,
    body: AccountPatch,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    return serializers.account(accounts.update_account(session, str(accountId), changes))


@router.post("/declared-balances", status_code=201)
def declare_balance(
    body: DeclaredBalanceInput, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    row = balances.declare_balance(
        session,
        balances.BalanceData(
            account_id=str(body.account_id),
            instrument_id=str(body.instrument_id),
            balance_date=body.balance_date,
            amount=body.amount,
            currency=body.currency,
        ),
    )
    return serializers.declared_balance(row)
