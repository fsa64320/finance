"""SC-009, contracts/export-format.md : exporter puis restaurer redonne les mêmes valeurs."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.api_helpers import API
from tests.data_helpers import fresh_client, populate, snapshot


def export(client: TestClient) -> dict:
    response = client.get(f"{API}/data/export")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_restoring_an_export_gives_identical_values(
    authed_client: TestClient, tmp_path: Path
) -> None:
    ids = populate(authed_client)
    before = snapshot(authed_client, ids)
    payload = export(authed_client)

    with fresh_client(tmp_path) as other:
        restored = other.post(f"{API}/data/restore", json=payload)
        assert restored.status_code == 204, restored.text
        assert snapshot(other, ids) == before


def test_the_export_is_complete_versioned_and_exact(authed_client: TestClient) -> None:
    populate(authed_client)
    payload = export(authed_client)
    assert payload["format_version"] == 1
    assert payload["exported_at"].endswith("Z")
    assert payload["reference_currency"] == "EUR"
    assert payload["settings"] == {"auto_fetch_prices": True, "export_reminder_days": 14}
    assert {a["name"] for a in payload["accounts"]} == {
        "PEA Courtier A",
        "Livret A",
        "Assurance-vie",
    }
    assert {i["name"] for i in payload["instruments"]} >= {"ETF Monde", "SCPI Exemple"}
    assert payload["prices"] and payload["declared_balances"] and payload["imports"]
    assert {r["kind"] for r in payload["rates"]} == {"LIVRET_A"}
    assert [m["name"] for m in payload["import_mappings"]] == []  # aucun enregistré dans ce jeu
    modified = next(
        t
        for t in payload["transactions"]
        if len(t["versions"]) == 2 and not t["versions"][1]["voided"]
    )
    assert [v["version"] for v in modified["versions"]] == [1, 2]
    assert (
        modified["versions"][0]["quantity"] == "10" and modified["versions"][1]["quantity"] == "12"
    )
    assert any(v["voided"] for t in payload["transactions"] for v in t["versions"])
    for t in payload["transactions"]:
        for version in t["versions"]:
            assert isinstance(version["cash_amount"], str)
            assert version["fees"] is not None


def test_the_export_holds_no_secret(authed_client: TestClient) -> None:
    populate(authed_client)
    text = json.dumps(export(authed_client)).lower()
    for word in ("password", "mot de passe", "salt", "kdf", "cipher"):
        assert word not in text


def test_the_export_is_a_downloadable_file(authed_client: TestClient) -> None:
    response = authed_client.get(f"{API}/data/export")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment") and "finance-export-" in disposition
    assert disposition.endswith('.json"')
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"


def test_exporting_records_the_date_for_the_reminder(authed_client: TestClient) -> None:
    assert authed_client.get(f"{API}/settings").json()["last_export_at"] is None
    export(authed_client)
    assert authed_client.get(f"{API}/settings").json()["last_export_at"] is not None


def test_an_empty_instance_round_trips(authed_client: TestClient, tmp_path: Path) -> None:
    payload = export(authed_client)
    with fresh_client(tmp_path) as other:
        assert other.post(f"{API}/data/restore", json=payload).status_code == 204
        assert other.get(f"{API}/accounts").json() == []
        assert (
            other.get(f"{API}/rates/livret-a").json()
            == authed_client.get(f"{API}/rates/livret-a").json()
        )


def test_a_restored_instance_exports_the_same_data(
    authed_client: TestClient, tmp_path: Path
) -> None:
    populate(authed_client)
    first = export(authed_client)
    with fresh_client(tmp_path) as other:
        other.post(f"{API}/data/restore", json=first)
        second = export(other)
    for key in ("exported_at",):
        first.pop(key), second.pop(key)
    assert second == first
