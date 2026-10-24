"""Appels d'API répétés par les tests de l'histoire US1."""

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def create_account(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "PEA",
        "name": "PEA Courtier A",
        "institution": "Courtier A",
        "opened_on": "2026-01-02",
    }
    body.update(overrides)
    response = client.post(f"{API}/accounts", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def create_instrument(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "ETF",
        "name": "ETF Monde",
        "isin": "IE00B4L5Y983",
        "currency": "EUR",
    }
    body.update(overrides)
    response = client.post(f"{API}/instruments", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def post_transaction(client: TestClient, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"currency": "EUR"}
    body.update(fields)
    response = client.post(f"{API}/transactions", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def account_detail(client: TestClient, account_id: str, as_of: str | None = None) -> dict[str, Any]:
    params = {"as_of": as_of} if as_of else {}
    response = client.get(f"{API}/accounts/{account_id}", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]
