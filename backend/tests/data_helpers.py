"""Instances d'application et jeux de données répétés par les tests de l'histoire US5."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from finance.config import Settings
from finance.main import create_app
from tests.api_helpers import API, create_account, create_instrument, post_transaction
from tests.conftest import API_PASSWORD
from tests.import_helpers import fixture, import_all


@contextmanager
def fresh_client(
    tmp_path: Path, name: str = "other", password: str = API_PASSWORD
) -> Iterator[TestClient]:
    """Une autre instance, initialisée et ouverte, avec son propre dossier de données."""
    settings = Settings(data_dir=tmp_path / name, host="127.0.0.1", port=8000)
    with TestClient(create_app(settings), base_url="http://testserver") as client:
        assert client.post(f"{API}/auth/setup", json={"password": password}).status_code == 204
        yield client


def populate(client: TestClient) -> dict[str, Any]:
    """Un jeu de données qui touche chaque table : comptes, actifs, versions, virement, prix,
    soldes déclarés, taux, import et paramétrage d'import."""
    pea = create_account(client, opened_on="2023-12-01")
    livret = create_account(
        client, type="LIVRET_A", name="Livret A", institution=None, opened_on="2025-01-01"
    )
    vie = create_account(client, type="ASSURANCE_VIE", name="Assurance-vie", opened_on="2025-06-01")
    etf = create_instrument(client, price_ticker="CW8.PA")
    scpi = create_instrument(client, kind="SCPI", name="SCPI Exemple", isin=None)
    fonds_euros = create_instrument(client, kind="EURO_FUND", name="Fonds en euros", isin=None)

    post_transaction(
        client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-05", amount="5000"
    )
    buy = post_transaction(
        client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-01-06",
        instrument_id=etf["id"],
        quantity="10",
        unit_price="90",
        fees="1.99",
    )
    buy_id = buy["transaction"]["id"]
    client.put(
        f"{API}/transactions/{buy_id}",
        json={
            "account_id": pea["id"],
            "type": "BUY",
            "trade_date": "2026-01-06",
            "instrument_id": etf["id"],
            "quantity": "12",
            "unit_price": "90",
            "fees": "1.99",
            "currency": "EUR",
        },
    )
    cancelled = post_transaction(
        client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-07", amount="10"
    )
    client.delete(f"{API}/transactions/{cancelled['transaction']['id']}")
    post_transaction(
        client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-02-02",
        instrument_id=scpi["id"],
        quantity="4",
        unit_price="250",
        fees="10",
    )
    post_transaction(
        client,
        account_id=pea["id"],
        type="DISTRIBUTION",
        trade_date="2026-03-15",
        instrument_id=scpi["id"],
        amount="12.5",
    )
    post_transaction(
        client, account_id=livret["id"], type="DEPOSIT", trade_date="2025-12-31", amount="1000"
    )
    transfer = client.post(
        f"{API}/transfers",
        json={
            "from_account_id": pea["id"],
            "to_account_id": livret["id"],
            "trade_date": "2026-03-01",
            "amount": "300",
            "currency": "EUR",
            "label": "Épargne",
        },
    )
    assert transfer.status_code == 201, transfer.text
    client.post(
        f"{API}/declared-balances",
        json={
            "account_id": vie["id"],
            "instrument_id": fonds_euros["id"],
            "balance_date": "2026-01-01",
            "amount": "5000",
            "currency": "EUR",
        },
    )
    for on, value, kind in (("2026-03-10", "92.5", "MARKET"),):
        client.post(
            f"{API}/prices",
            json={
                "instrument_id": etf["id"],
                "price_date": on,
                "kind": kind,
                "value": value,
                "currency": "EUR",
            },
        )
    for kind, value in (("SUBSCRIPTION", "250"), ("REDEMPTION", "228.4")):
        client.post(
            f"{API}/prices",
            json={
                "instrument_id": scpi["id"],
                "price_date": "2026-03-10",
                "kind": kind,
                "value": value,
                "currency": "EUR",
            },
        )
    client.post(f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": "1.5"})
    client.patch(f"{API}/settings", json={"auto_fetch_prices": True, "export_reminder_days": 14})
    summary = import_all(
        client, pea["id"], fixture("doublons_meme_jour.csv"), {"FR0000000010": "ETF"}
    )
    assert summary["rows_added"] == 3
    return {"pea": pea, "livret": livret, "vie": vie, "etf": etf, "scpi": scpi}


def snapshot(client: TestClient, ids: dict[str, Any], as_of: str = "2026-06-30") -> dict[str, Any]:
    """Tout ce que l'application montre de la valeur : à comparer entre deux instances."""

    def get(path: str, **params: str) -> Any:
        response = client.get(f"{API}{path}", params=params)
        assert response.status_code == 200, (path, response.text)
        return response.json()

    accounts = get("/accounts", include_closed="true", as_of=as_of)
    return {
        "accounts": accounts,
        "details": {a["id"]: get(f"/accounts/{a['id']}", as_of=as_of) for a in accounts},
        "transactions": {
            a["id"]: get("/transactions", account_id=a["id"], include_voided="true", limit="500")[
                "items"
            ]
            for a in accounts
        },
        "summary": get("/dashboard/summary", as_of=as_of),
        "allocation": get("/dashboard/allocation", as_of=as_of),
        "series": get("/dashboard/series", period="1y"),
        "instruments": get("/instruments"),
        "mappings": get("/import-mappings"),
        "livret_rates": get("/rates/livret-a"),
        "settings": {k: v for k, v in get("/settings").items() if k != "last_export_at"},
        "prices": {i["id"]: get("/prices", instrument_id=i["id"]) for i in get("/instruments")},
    }
