"""T118 : /data/export et /data/restore respectent le contrat openapi.yaml."""

from fastapi.testclient import TestClient

from tests.api_helpers import API
from tests.data_helpers import populate
from tests.integration.test_restore_rules import MINIMAL, account


def test_export_is_a_json_object_with_the_documented_sections(authed_client: TestClient) -> None:
    populate(authed_client)
    response = authed_client.get(f"{API}/data/export")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    for section in (
        "format_version",
        "exported_at",
        "reference_currency",
        "settings",
        "accounts",
        "instruments",
        "transactions",
        "prices",
        "declared_balances",
        "rates",
        "imports",
        "import_mappings",
    ):
        assert section in body


def test_restore_answers_with_the_documented_statuses(authed_client: TestClient) -> None:
    assert authed_client.post(f"{API}/data/restore", json={"format_version": 9}).status_code == 422
    filled = {**MINIMAL, "accounts": [account()]}
    assert authed_client.post(f"{API}/data/restore", json=filled).status_code == 204
    refused = authed_client.post(f"{API}/data/restore", json=filled)
    assert refused.status_code == 409
    assert refused.headers["content-type"].startswith("application/json")
    assert {"code", "message"} <= set(refused.json())


def test_the_error_format_is_the_common_one(authed_client: TestClient) -> None:
    body = authed_client.post(f"{API}/data/restore", json={"format_version": 9}).json()
    assert body["code"] == "validation_error" and body["details"]
