"""T046 : les réponses réelles de l'API respectent les schémas du contrat openapi.yaml."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tests.api_helpers import API, create_account, create_instrument, post_transaction

CONTRACT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[3]
        / "specs/001-wealth-dashboard-foundation/contracts/openapi.yaml"
    ).read_text(encoding="utf-8")
)
REGISTRY = Registry().with_resource(
    "urn:contract", Resource.from_contents(CONTRACT, default_specification=DRAFT202012)
)


def conforms(payload: Any, schema_name: str) -> None:
    schema = {"$ref": f"urn:contract#/components/schemas/{schema_name}"}
    Draft202012Validator(schema, registry=REGISTRY).validate(payload)


@pytest.fixture
def seeded(authed_client: TestClient) -> dict[str, Any]:
    pea = create_account(authed_client)
    etf = create_instrument(authed_client)
    deposit = post_transaction(
        authed_client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-05", amount="1000"
    )
    buy = post_transaction(
        authed_client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-01-06",
        instrument_id=etf["id"],
        quantity="10",
        unit_price="90",
        fees="1.99",
    )
    return {"pea": pea, "etf": etf, "deposit": deposit, "buy": buy}


def test_account_responses(authed_client: TestClient, seeded: dict[str, Any]) -> None:
    pea = seeded["pea"]
    conforms(pea, "Account")
    listed = authed_client.get(f"{API}/accounts")
    assert listed.status_code == 200
    for item in listed.json():
        conforms(item, "AccountSummary")
    detail = authed_client.get(f"{API}/accounts/{pea['id']}", params={"as_of": "2026-01-31"})
    conforms(detail.json(), "AccountDetail")
    patched = authed_client.patch(f"{API}/accounts/{pea['id']}", json={"institution": "Autre"})
    assert patched.status_code == 200
    conforms(patched.json(), "Account")


def test_instrument_responses(authed_client: TestClient, seeded: dict[str, Any]) -> None:
    etf = seeded["etf"]
    conforms(etf, "Instrument")
    for item in authed_client.get(f"{API}/instruments").json():
        conforms(item, "Instrument")
    patched = authed_client.patch(f"{API}/instruments/{etf['id']}", json={"price_ticker": "CW8.PA"})
    assert patched.status_code == 200
    conforms(patched.json(), "Instrument")


def test_transaction_responses(authed_client: TestClient, seeded: dict[str, Any]) -> None:
    buy = seeded["buy"]
    conforms(seeded["deposit"], "TransactionResult")
    conforms(buy, "TransactionResult")
    listed = authed_client.get(f"{API}/transactions").json()
    for item in listed["items"]:
        conforms(item, "Transaction")
    detail = authed_client.get(f"{API}/transactions/{buy['transaction']['id']}")
    conforms(detail.json(), "TransactionWithHistory")
    body = {
        "account_id": seeded["pea"]["id"],
        "type": "BUY",
        "trade_date": "2026-01-06",
        "instrument_id": seeded["etf"]["id"],
        "quantity": "11",
        "unit_price": "90",
        "fees": "1.99",
        "currency": "EUR",
    }
    edited = authed_client.put(f"{API}/transactions/{buy['transaction']['id']}", json=body)
    assert edited.status_code == 200
    conforms(edited.json(), "TransactionResult")
    cancelled = authed_client.delete(f"{API}/transactions/{buy['transaction']['id']}")
    assert cancelled.status_code == 200
    conforms(cancelled.json(), "TransactionResult")
    assert cancelled.json()["transaction"]["voided"] is True


def test_transfer_and_declared_balance_responses(
    authed_client: TestClient, seeded: dict[str, Any]
) -> None:
    livret = create_account(authed_client, type="LIVRET_A", name="Livret A")
    transfer = authed_client.post(
        f"{API}/transfers",
        json={
            "from_account_id": seeded["pea"]["id"],
            "to_account_id": livret["id"],
            "trade_date": "2026-03-01",
            "amount": "100",
            "currency": "EUR",
        },
    )
    assert transfer.status_code == 201
    payload = transfer.json()
    conforms(payload["out"], "TransactionResult")
    conforms(payload["in"], "TransactionResult")
    assert payload["out"]["transaction"]["transfer_group_id"] == payload["transfer_group_id"]
    fund = create_instrument(authed_client, kind="EURO_FUND", name="Fonds en euros", isin=None)
    declared = authed_client.post(
        f"{API}/declared-balances",
        json={
            "account_id": seeded["pea"]["id"],
            "instrument_id": fund["id"],
            "balance_date": "2026-01-01",
            "amount": "5000",
            "currency": "EUR",
        },
    )
    assert declared.status_code == 201
    conforms(declared.json(), "DeclaredBalance")


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("GET", "/accounts/00000000-0000-4000-8000-000000000000", None, 404),
        ("GET", "/accounts/pas-un-uuid", None, 422),
        ("POST", "/accounts", {"type": "PEA", "name": "", "opened_on": "2026-01-02"}, 422),
        ("POST", "/accounts", {"type": "AUTRE", "name": "x", "opened_on": "2026-01-02"}, 422),
        ("PATCH", "/accounts/00000000-0000-4000-8000-000000000000", {"name": "x"}, 404),
        ("PATCH", "/instruments/00000000-0000-4000-8000-000000000000", {"name": "x"}, 404),
        ("GET", "/transactions/00000000-0000-4000-8000-000000000000", None, 404),
        ("DELETE", "/transactions/00000000-0000-4000-8000-000000000000", None, 404),
        ("GET", "/transactions?limit=0", None, 422),
    ],
)
def test_error_responses_use_the_error_schema(
    authed_client: TestClient, method: str, path: str, body: Any, status: int
) -> None:
    response = authed_client.request(method, f"{API}{path}", json=body)
    assert response.status_code == status, response.text
    conforms(response.json(), "Error")


def test_duplicate_open_account_name_is_a_conflict_with_the_error_schema(
    authed_client: TestClient, seeded: dict[str, Any]
) -> None:
    response = authed_client.post(
        f"{API}/accounts",
        json={"type": "CTO", "name": seeded["pea"]["name"], "opened_on": "2026-01-02"},
    )
    assert response.status_code == 409
    conforms(response.json(), "Error")


def test_duplicate_isin_is_a_conflict_with_the_error_schema(
    authed_client: TestClient, seeded: dict[str, Any]
) -> None:
    response = authed_client.post(
        f"{API}/instruments",
        json={"kind": "ETF", "name": "Autre", "isin": seeded["etf"]["isin"], "currency": "EUR"},
    )
    assert response.status_code == 409
    conforms(response.json(), "Error")
