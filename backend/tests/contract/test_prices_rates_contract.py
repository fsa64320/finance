"""T099 : /prices, /prices/refresh, /rates/livret-a, /settings et les suggestions de ticker."""

from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from tests.api_helpers import API, create_instrument
from tests.contract.test_accounts_transactions_contract import CONTRACT, conforms
from tests.provider_fakes import FakePrices, install, recent


def conforms_to_response(payload: Any, path: str, method: str, status: str) -> None:
    schema = CONTRACT["paths"][path][method]["responses"][status]["content"]["application/json"][
        "schema"
    ]
    if "$ref" in schema:
        conforms(payload, schema["$ref"].rsplit("/", 1)[1])
    else:
        Draft202012Validator({**schema, "components": CONTRACT["components"]}).validate(payload)


def test_settings_conform(authed_client: TestClient) -> None:
    body = authed_client.get(f"{API}/settings").json()
    conforms(body, "Settings")
    patched = authed_client.patch(f"{API}/settings", json={"auto_fetch_prices": True})
    conforms(patched.json(), "Settings")
    assert patched.json()["auto_fetch_prices"] is True


def test_manual_price_and_list_conform(authed_client: TestClient) -> None:
    etf = create_instrument(authed_client)
    created = authed_client.post(
        f"{API}/prices",
        json={
            "instrument_id": etf["id"],
            "price_date": "2026-01-10",
            "kind": "MARKET",
            "value": "90.2",
            "currency": "EUR",
        },
    )
    assert created.status_code == 201, created.text
    conforms(created.json(), "Price")
    listed = authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]})
    assert listed.status_code == 200 and len(listed.json()) == 1
    for item in listed.json():
        conforms(item, "Price")


def test_livret_rates_conform(authed_client: TestClient) -> None:
    created = authed_client.post(
        f"{API}/rates/livret-a", json={"effective_from": "2026-02-01", "value": "1.7"}
    )
    assert created.status_code == 201, created.text
    conforms(created.json(), "LivretARate")
    for item in authed_client.get(f"{API}/rates/livret-a").json():
        conforms(item, "LivretARate")


def test_refresh_result_conforms_whatever_the_outcome(authed_client: TestClient) -> None:
    install(authed_client, prices=FakePrices({"CW8.PA": [(recent(), "90")]}))
    create_instrument(authed_client, price_ticker="CW8.PA")
    disabled = authed_client.post(f"{API}/prices/refresh")
    assert disabled.status_code == 200
    conforms_to_response(disabled.json(), "/prices/refresh", "post", "200")
    authed_client.patch(f"{API}/settings", json={"auto_fetch_prices": True})
    enabled = authed_client.post(f"{API}/prices/refresh")
    conforms_to_response(enabled.json(), "/prices/refresh", "post", "200")
    assert {s["status"] for s in enabled.json()["sources"]} == {"ok"}


def test_ticker_suggestions_conform(authed_client: TestClient) -> None:
    install(authed_client)
    etf = create_instrument(authed_client)
    authed_client.patch(f"{API}/settings", json={"auto_fetch_prices": True})
    response = authed_client.post(f"{API}/instruments/{etf['id']}/ticker-suggestions")
    assert response.status_code == 200
    conforms_to_response(
        response.json(), "/instruments/{instrumentId}/ticker-suggestions", "post", "200"
    )
