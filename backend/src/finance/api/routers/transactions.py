"""Routes des opérations et des virements (contrat : tag `transactions`)."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.schemas import TransactionInput, TransferInput
from finance.domain.enums import TransactionType
from finance.services import transactions, transfers
from finance.services.transactions import TransactionData

router = APIRouter(tags=["transactions"])

NOT_FOUND = {"description": "Opération introuvable"}


def to_data(body: TransactionInput) -> TransactionData:
    return TransactionData(
        account_id=str(body.account_id),
        type=TransactionType(body.type.value),
        trade_date=body.trade_date,
        currency=body.currency,
        instrument_id=None if body.instrument_id is None else str(body.instrument_id),
        quantity=body.quantity,
        unit_price=body.unit_price,
        amount=body.amount,
        fees=Decimal(0) if body.fees is None else body.fees,
        unlock_date=body.unlock_date,
        label=body.label,
    )


@router.get("/transactions")
def list_transactions(
    account_id: UUID | None = None,
    instrument_id: UUID | None = None,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    include_voided: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = None,
    session: Session = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    page = transactions.list_transactions(
        session,
        account_id=None if account_id is None else str(account_id),
        instrument_id=None if instrument_id is None else str(instrument_id),
        date_from=date_from,
        date_to=date_to,
        include_voided=include_voided,
        limit=limit,
        cursor=cursor,
    )
    return {
        "items": [serializers.transaction(row) for row in page.items],
        "next_cursor": page.next_cursor,
    }


@router.post("/transactions", status_code=201)
def create_transaction(
    body: TransactionInput, session: Session = Depends(get_db_session, scope="function")
) -> dict[str, Any]:
    return serializers.transaction_result(transactions.create_transaction(session, to_data(body)))


@router.get("/transactions/{transactionId}", responses={404: NOT_FOUND})
def get_transaction(
    transactionId: UUID,
    session: Session = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    current, versions = transactions.get_transaction(session, str(transactionId))
    return {
        "current": serializers.transaction(current),
        "versions": [serializers.transaction(row) for row in versions],
    }


@router.put("/transactions/{transactionId}", responses={404: NOT_FOUND})
def update_transaction(
    transactionId: UUID,
    body: TransactionInput,
    session: Session = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    outcome = transactions.update_transaction(session, str(transactionId), to_data(body))
    return serializers.transaction_result(outcome)


@router.delete("/transactions/{transactionId}", responses={404: NOT_FOUND})
def void_transaction(
    transactionId: UUID,
    session: Session = Depends(get_db_session, scope="function"),
) -> dict[str, Any]:
    return serializers.transaction_result(
        transactions.void_transaction(session, str(transactionId))
    )


@router.post("/transfers", status_code=201)
def create_transfer(
    body: TransferInput, session: Session = Depends(get_db_session, scope="function")
) -> dict[str, Any]:
    outcome = transfers.create_transfer(
        session,
        transfers.TransferData(
            from_account_id=str(body.from_account_id),
            to_account_id=str(body.to_account_id),
            trade_date=body.trade_date,
            amount=body.amount,
            currency=body.currency,
            label=body.label,
        ),
    )
    return serializers.transfer_result(outcome)
