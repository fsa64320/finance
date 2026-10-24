"""T086 : les réponses d'import respectent le contrat openapi.yaml."""

from typing import Any

from fastapi.testclient import TestClient

from tests.api_helpers import API, create_account
from tests.contract.test_accounts_transactions_contract import conforms
from tests.import_helpers import COLUMNS, commit, fixture, preview, resolutions

MAPPING = {
    "name": "Courtier A",
    "delimiter": ";",
    "encoding": "windows-1252",
    "date_format": "%d/%m/%Y",
    "decimal_separator": ",",
    "columns": COLUMNS,
}


def test_mapping_creation_and_list_conform(authed_client: TestClient) -> None:
    created = authed_client.post(f"{API}/import-mappings", json=MAPPING)
    assert created.status_code == 201, created.text
    conforms(created.json(), "ImportMapping")
    listed = authed_client.get(f"{API}/import-mappings")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created.json()["id"]]
    for item in listed.json():
        conforms(item, "ImportMapping")


def test_mapping_names_are_unique(authed_client: TestClient) -> None:
    assert authed_client.post(f"{API}/import-mappings", json=MAPPING).status_code == 201
    assert authed_client.post(f"{API}/import-mappings", json=MAPPING).status_code == 409


def test_mapping_validation(authed_client: TestClient) -> None:
    for change in (
        {"delimiter": ";;"},
        {"decimal_separator": ";"},
        {"encoding": "pas-un-encodage"},
        {"date_format": "pas de format"},
        {"name": " "},
        {"columns": {"trade_date": "Date"}},
        {"columns": {"trade_date": "Date", "type": "Op", "inconnu": "X"}},
    ):
        response = authed_client.post(f"{API}/import-mappings", json={**MAPPING, **change})
        assert response.status_code == 422, change


def test_preview_and_commit_conform(authed_client: TestClient) -> None:
    account_id = create_account(authed_client, opened_on="2023-12-01")["id"]
    shown = preview(authed_client, account_id, fixture("lignes_invalides.csv"))
    assert shown.status_code == 200, shown.text
    body: dict[str, Any] = shown.json()
    conforms(body, "ImportPreview")
    assert body["rows_rejected"] and body["unknown_instruments"] and body["sample"]

    done = commit(
        authed_client,
        body["preview_id"],
        confirm_rejected=True,
        instrument_resolutions=resolutions(body, {}),
    )
    assert done.status_code == 201, done.text
    conforms(done.json(), "ImportResult")


def test_commit_validates_its_body(authed_client: TestClient) -> None:
    assert authed_client.post(f"{API}/imports/commit", json={}).status_code == 422
