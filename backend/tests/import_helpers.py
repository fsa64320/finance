"""Appels d'API et constructeurs de fichiers répétés par les tests de l'histoire US3."""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from tests.api_helpers import API

FIXTURES = Path(__file__).parent / "fixtures" / "csv"
HEADER = "Date;Opération;Libellé;ISIN;Quantité;Cours;Montant;Frais;Référence"
COLUMNS = {
    "trade_date": "Date",
    "type": "Opération",
    "label": "Libellé",
    "instrument_name": "Libellé",
    "isin": "ISIN",
    "quantity": "Quantité",
    "unit_price": "Cours",
    "amount": "Montant",
    "fees": "Frais",
    "external_id": "Référence",
}
ETF_ISIN = "FR0000000010"
ACTION_ISIN = "FR0000000028"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def csv_bytes(*lines: str) -> bytes:
    return "\n".join([HEADER, *lines, ""]).encode("windows-1252")


def preview(
    client: TestClient,
    account_id: str,
    content: bytes,
    *,
    columns: dict[str, str] | None = COLUMNS,
    file_name: str = "export.csv",
    **form: str,
) -> Response:
    data: dict[str, str] = {"account_id": account_id, **form}
    if columns is not None:
        data["columns"] = json.dumps(columns)
    return client.post(
        f"{API}/imports/preview",
        data=data,
        files={"file": (file_name, content, "text/csv")},
    )


def commit(client: TestClient, preview_id: str, **body: Any) -> Response:
    payload: dict[str, Any] = {"preview_id": preview_id, "confirm_rejected": False}
    payload.update(body)
    return client.post(f"{API}/imports/commit", json=payload)


def resolutions(body: dict[str, Any], kinds: dict[str, str]) -> list[dict[str, str]]:
    """Une résolution « créer » par actif inconnu ; `kinds` associe l'ISIN ou le nom à un type."""
    result = []
    for item in body["unknown_instruments"]:
        kind = kinds.get(item["isin"] or item["name"], "ETF")
        result.append({"key": item["key"], "action": "create", "kind": kind})
    return result


def import_all(
    client: TestClient, account_id: str, content: bytes, kinds: dict[str, str] | None = None
) -> dict[str, Any]:
    """Aperçu puis validation, en créant les actifs inconnus ; renvoie le résumé."""
    shown = preview(client, account_id, content)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    done = commit(
        client,
        body["preview_id"],
        confirm_rejected=True,
        instrument_resolutions=resolutions(body, kinds or {}),
    )
    assert done.status_code == 201, done.text
    return done.json()  # type: ignore[no-any-return]


def transactions(client: TestClient, account_id: str) -> list[dict[str, Any]]:
    response = client.get(f"{API}/transactions", params={"account_id": account_id, "limit": 500})
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


def instruments(client: TestClient) -> list[dict[str, Any]]:
    response = client.get(f"{API}/instruments")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]
