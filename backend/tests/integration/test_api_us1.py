"""API de l'histoire US1 : accès, validation des entrées et formats."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import API, create_account, create_instrument, post_transaction

ZERO = "00000000-0000-4000-8000-000000000000"

PROTECTED = [
    ("GET", "/accounts"),
    ("POST", "/accounts"),
    ("GET", f"/accounts/{ZERO}"),
    ("PATCH", f"/accounts/{ZERO}"),
    ("GET", "/instruments"),
    ("POST", "/instruments"),
    ("PATCH", f"/instruments/{ZERO}"),
    ("GET", "/transactions"),
    ("POST", "/transactions"),
    ("GET", f"/transactions/{ZERO}"),
    ("PUT", f"/transactions/{ZERO}"),
    ("DELETE", f"/transactions/{ZERO}"),
    ("POST", "/transfers"),
    ("POST", "/declared-balances"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_route_needs_a_session(authed_client: TestClient, method: str, path: str) -> None:
    anonymous = TestClient(authed_client.app, base_url="http://testserver")
    response = anonymous.request(method, f"{API}{path}", json={})
    assert response.status_code == 401
    assert response.json()["code"] == "session_required"


def test_amounts_must_be_decimal_strings_not_json_numbers(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    response = authed_client.post(
        f"{API}/transactions",
        json={
            "account_id": pea["id"],
            "type": "DEPOSIT",
            "trade_date": "2026-01-05",
            "amount": 1000.5,
            "currency": "EUR",
        },
    )
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "amount"


def test_unknown_fields_are_refused(authed_client: TestClient) -> None:
    response = authed_client.post(
        f"{API}/accounts",
        json={"type": "PEA", "name": "x", "opened_on": "2026-01-02", "solde": "10"},
    )
    assert response.status_code == 422


def test_business_rule_violations_come_back_as_field_details(authed_client: TestClient) -> None:
    livret = create_account(authed_client, type="LIVRET_A", name="Livret A")
    etf = create_instrument(authed_client)
    response = authed_client.post(
        f"{API}/transactions",
        json={
            "account_id": livret["id"],
            "type": "BUY",
            "trade_date": "2026-01-05",
            "instrument_id": etf["id"],
            "quantity": "1",
            "unit_price": "10",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["details"][0] == {
        "field": "type",
        "message": "Un Livret A ne contient que de la trésorerie : pas d'achat ni de vente.",
    }


def test_invalid_isin_is_reported_on_its_field(authed_client: TestClient) -> None:
    response = authed_client.post(
        f"{API}/instruments",
        json={"kind": "ETF", "name": "x", "isin": "IE00B4L5Y984", "currency": "EUR"},
    )
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "isin"


def test_account_creation_applies_defaults(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    assert (pea["currency"], pea["closed_on"]) == ("EUR", None)
    assert pea["settings"] == {"deposit_cap": "150000"}


def test_closed_accounts_are_hidden_unless_requested(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    closed = authed_client.patch(f"{API}/accounts/{pea['id']}", json={"closed_on": "2026-06-30"})
    assert closed.status_code == 200 and closed.json()["closed_on"] == "2026-06-30"
    assert authed_client.get(f"{API}/accounts").json() == []
    shown = authed_client.get(f"{API}/accounts", params={"include_closed": "true"}).json()
    assert [a["id"] for a in shown] == [pea["id"]]


def test_account_detail_reports_the_pea_cap_and_warnings(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    etf = create_instrument(authed_client)
    post_transaction(
        authed_client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-05", amount="1000"
    )
    post_transaction(
        authed_client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-01-06",
        instrument_id=etf["id"],
        quantity="10",
        unit_price="90",
    )
    detail: dict[str, Any] = authed_client.get(
        f"{API}/accounts/{pea['id']}", params={"as_of": "2026-01-31"}
    ).json()
    assert detail["deposit_cap_usage"] == {
        "deposited": "1000",
        "cap": "150000",
        "remaining": "149000",
        "exceeded": False,
    }
    assert [w["code"] for w in detail["warnings"]] == ["price_missing"]
    assert detail["positions"][0]["kind"] == "ETF"


def test_bad_as_of_is_a_validation_error(authed_client: TestClient) -> None:
    assert authed_client.get(f"{API}/accounts", params={"as_of": "hier"}).status_code == 422


def test_transaction_warnings_are_returned_with_the_result(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    etf = create_instrument(authed_client)
    result = post_transaction(
        authed_client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-01-06",
        instrument_id=etf["id"],
        quantity="10",
        unit_price="90",
    )
    assert result["transaction"]["cash_amount"] == "-900"
    assert any("liquidités" in warning for warning in result["warnings"])


def test_transfer_legs_cannot_be_edited_through_put(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    livret = create_account(authed_client, type="LIVRET_A", name="Livret A")
    transfer = authed_client.post(
        f"{API}/transfers",
        json={
            "from_account_id": pea["id"],
            "to_account_id": livret["id"],
            "trade_date": "2026-03-01",
            "amount": "100",
            "currency": "EUR",
        },
    ).json()
    leg_id = transfer["out"]["transaction"]["id"]
    response = authed_client.put(
        f"{API}/transactions/{leg_id}",
        json={
            "account_id": pea["id"],
            "type": "DEPOSIT",
            "trade_date": "2026-03-01",
            "amount": "1",
            "currency": "EUR",
        },
    )
    assert response.status_code == 422
    cancelled = authed_client.delete(f"{API}/transactions/{leg_id}")
    assert cancelled.status_code == 200
    other_leg = transfer["in"]["transaction"]["id"]
    assert authed_client.get(f"{API}/transactions/{other_leg}").json()["current"]["voided"] is True


def test_commit_happens_only_on_success(authed_client: TestClient) -> None:
    pea = create_account(authed_client)
    bad = authed_client.post(
        f"{API}/transactions",
        json={
            "account_id": pea["id"],
            "type": "DEPOSIT",
            "trade_date": "2025-01-01",
            "amount": "10",
            "currency": "EUR",
        },
    )
    assert bad.status_code == 422
    assert authed_client.get(f"{API}/transactions").json()["items"] == []
