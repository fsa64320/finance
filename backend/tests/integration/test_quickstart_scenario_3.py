"""T047 : étapes a à g de quickstart.md section 3, de bout en bout sur la base chiffrée."""

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from tests.api_helpers import (
    API,
    account_detail,
    create_account,
    create_instrument,
    post_transaction,
)


def d(value: str) -> Decimal:
    return Decimal(value)


def position(detail: dict[str, Any], instrument_id: str) -> dict[str, Any]:
    return next(p for p in detail["positions"] if p["instrument_id"] == instrument_id)


def test_quickstart_section_3(authed_client: TestClient) -> None:
    client = authed_client

    # a. Créer un PEA « PEA Courtier A » ouvert le 2026-01-02 : compte à 0 €
    pea = create_account(client)
    detail = account_detail(client, pea["id"], "2026-01-31")
    assert (detail["value"], detail["cash"], detail["positions"]) == ("0", "0", [])

    # b. Versement de 1 000 € le 2026-01-05 : liquidités 1 000 €
    post_transaction(
        client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-05", amount="1000"
    )
    assert account_detail(client, pea["id"], "2026-01-31")["cash"] == "1000"

    # c. ETF Monde, achat de 10 parts à 90 € avec 1,99 € de frais le 2026-01-06
    etf = create_instrument(client)
    bought = post_transaction(
        client,
        account_id=pea["id"],
        type="BUY",
        trade_date="2026-01-06",
        instrument_id=etf["id"],
        quantity="10",
        unit_price="90",
        fees="1.99",
    )
    assert bought["transaction"]["cash_amount"] == "-901.99"
    detail = account_detail(client, pea["id"], "2026-01-31")
    held = position(detail, etf["id"])
    assert (held["quantity"], held["unit_cost"]) == ("10", "90.199")
    assert detail["cash"] == "98.01"
    # sans prix connu, la position est valorisée à son prix de revient et signalée
    assert held["estimated"] is True and held["value"] == "901.99"
    assert detail["value"] == "1000" and detail["estimated"] is True

    # d. Livret A de 3 000 € (versement), puis retrait de 500 € : solde 2 500 €
    #    (taux à 0 % pour garder des totaux ronds : les intérêts estimés sont testés à part)
    client.post(f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": "0"})
    livret = create_account(client, type="LIVRET_A", name="Livret A", institution="Banque")
    post_transaction(
        client, account_id=livret["id"], type="DEPOSIT", trade_date="2026-01-03", amount="3000"
    )
    post_transaction(
        client, account_id=livret["id"], type="WITHDRAWAL", trade_date="2026-01-10", amount="500"
    )
    assert account_detail(client, livret["id"], "2026-01-31")["cash"] == "2500"

    # e. Assurance-vie avec un fonds en euros, solde déclaré de 5 000 € au 2026-01-01
    vie = create_account(client, type="ASSURANCE_VIE", name="Assurance-vie", opened_on="2025-06-01")
    euro_fund = create_instrument(client, kind="EURO_FUND", name="Fonds en euros", isin=None)
    declared = client.post(
        f"{API}/declared-balances",
        json={
            "account_id": vie["id"],
            "instrument_id": euro_fund["id"],
            "balance_date": "2026-01-01",
            "amount": "5000",
            "currency": "EUR",
        },
    )
    assert declared.status_code == 201, declared.text
    detail = account_detail(client, vie["id"], "2026-01-31")
    assert position(detail, euro_fund["id"])["value"] == "5000"
    assert detail["value"] == "5000"

    # f. Virement de 500 € du PEA vers le Livret A : patrimoine inchangé
    def total(as_of: str) -> Decimal:
        accounts = client.get(f"{API}/accounts", params={"as_of": as_of}).json()
        return sum((d(a["value"]) for a in accounts), Decimal(0))

    before = total("2026-03-31")
    transfer = client.post(
        f"{API}/transfers",
        json={
            "from_account_id": pea["id"],
            "to_account_id": livret["id"],
            "trade_date": "2026-03-01",
            "amount": "500",
            "currency": "EUR",
        },
    )
    assert transfer.status_code == 201, transfer.text
    legs = transfer.json()
    assert legs["out"]["transaction"]["cash_amount"] == "-500"
    assert legs["in"]["transaction"]["cash_amount"] == "500"
    assert account_detail(client, pea["id"], "2026-03-31")["cash"] == "-401.99"
    assert account_detail(client, livret["id"], "2026-03-31")["cash"] == "3000"
    assert total("2026-03-31") == before

    # g. Modifier l'achat de l'étape c (quantité 12) : version à jour, ancienne conservée
    edited = client.put(
        f"{API}/transactions/{bought['transaction']['id']}",
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
    assert edited.status_code == 200, edited.text
    assert edited.json()["transaction"]["version"] == 2
    detail = account_detail(client, pea["id"], "2026-01-31")
    assert position(detail, etf["id"])["quantity"] == "12"

    history = client.get(f"{API}/transactions/{bought['transaction']['id']}").json()
    assert history["current"]["quantity"] == "12"
    assert [(v["version"], v["quantity"]) for v in history["versions"]] == [(1, "10"), (2, "12")]

    listed = client.get(f"{API}/transactions", params={"account_id": pea["id"]}).json()
    assert [t["version"] for t in listed["items"] if t["type"] == "BUY"] == [2]
