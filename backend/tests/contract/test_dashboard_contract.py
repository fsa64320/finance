"""T069 : les réponses du tableau de bord respectent le contrat openapi.yaml."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from tests.api_helpers import API, create_account, create_instrument, post_transaction
from tests.contract.test_accounts_transactions_contract import CONTRACT, REGISTRY, conforms


def response_schema(path: str) -> dict[str, Any]:
    schema = CONTRACT["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    return schema  # type: ignore[no-any-return]


def conforms_to_path(payload: Any, path: str) -> None:
    schema = response_schema(path)
    if "$ref" in schema:
        conforms(payload, schema["$ref"].rsplit("/", 1)[1])
    else:
        Draft202012Validator(schema, registry=REGISTRY).validate(payload)


@pytest.fixture
def seeded(authed_client: TestClient) -> None:
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
        fees="1.99",
    )


def test_summary_conforms(authed_client: TestClient, seeded: None) -> None:
    response = authed_client.get(f"{API}/dashboard/summary", params={"as_of": "2026-01-31"})
    assert response.status_code == 200
    body = response.json()
    conforms_to_path(body, "/dashboard/summary")
    assert body["net_worth"] == "1000"
    assert body["excludes_debts"] is True
    assert body["estimated"] is True
    assert body["notices"][0]["kind"] == "stale_price"


def test_series_conforms(authed_client: TestClient, seeded: None) -> None:
    response = authed_client.get(f"{API}/dashboard/series", params={"period": "1y"})
    assert response.status_code == 200
    body = response.json()
    conforms_to_path(body, "/dashboard/series")
    assert body["points"][-1]["value"] == "1000"


@pytest.mark.parametrize("period", ["1m", "3m", "1y", "5y", "all"])
def test_every_period_is_accepted(authed_client: TestClient, seeded: None, period: str) -> None:
    assert (
        authed_client.get(f"{API}/dashboard/series", params={"period": period}).status_code == 200
    )


def test_period_defaults_to_one_year(authed_client: TestClient, seeded: None) -> None:
    default = authed_client.get(f"{API}/dashboard/series").json()
    explicit = authed_client.get(f"{API}/dashboard/series", params={"period": "1y"}).json()
    assert default == explicit


def test_allocation_conforms(authed_client: TestClient, seeded: None) -> None:
    response = authed_client.get(f"{API}/dashboard/allocation", params={"as_of": "2026-01-31"})
    assert response.status_code == 200
    body = response.json()
    conforms_to_path(body, "/dashboard/allocation")
    assert {s["asset_class"] for s in body["slices"]} == {"equities_etf", "cash"}
    assert sum(float(s["weight_percent"]) for s in body["slices"]) == pytest.approx(100)


def test_empty_instance_returns_neutral_values(authed_client: TestClient) -> None:
    summary = authed_client.get(f"{API}/dashboard/summary").json()
    assert (summary["net_worth"], summary["estimated"], summary["notices"]) == ("0", False, [])
    assert authed_client.get(f"{API}/dashboard/series").json()["points"] == []
    assert authed_client.get(f"{API}/dashboard/allocation").json()["slices"] == []


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/dashboard/summary", {"as_of": "hier"}),
        ("/dashboard/series", {"period": "7y"}),
        ("/dashboard/allocation", {"as_of": "31/12/2026"}),
    ],
)
def test_bad_parameters_use_the_error_schema(
    authed_client: TestClient, path: str, params: dict[str, str]
) -> None:
    response = authed_client.get(f"{API}{path}", params=params)
    assert response.status_code == 422
    conforms(response.json(), "Error")


@pytest.mark.parametrize(
    "path", ["/dashboard/summary", "/dashboard/series", "/dashboard/allocation"]
)
def test_dashboard_needs_a_session(authed_client: TestClient, path: str) -> None:
    anonymous = TestClient(authed_client.app, base_url="http://testserver")
    assert anonymous.get(f"{API}{path}").status_code == 401
