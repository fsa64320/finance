"""US4 de bout en bout par l'API : prix manuels, récupération, taux, SCPI, Livret A, devises."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from finance.prices.base import FetchedRate
from tests.api_helpers import API, create_account, create_instrument, post_transaction
from tests.provider_fakes import FakePrices, FakeRates, FakeTickers, install, recent

ISIN_SCPI = "FR0000000010"


def settings(client: TestClient, **patch: object) -> dict:
    response = client.patch(f"{API}/settings", json=patch)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def price_input(
    instrument_id: str, on: str, value: str, kind: str = "MARKET", currency: str = "EUR"
) -> dict:
    return {
        "instrument_id": instrument_id,
        "price_date": on,
        "kind": kind,
        "value": value,
        "currency": currency,
    }


def detail(client: TestClient, account_id: str, as_of: str) -> dict:
    response = client.get(f"{API}/accounts/{account_id}", params={"as_of": as_of})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def summary(client: TestClient, as_of: str) -> dict:
    response = client.get(f"{API}/dashboard/summary", params={"as_of": as_of})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


class TestSettings:
    def test_defaults_keep_everything_local(self, authed_client: TestClient) -> None:
        body = authed_client.get(f"{API}/settings").json()
        assert body["reference_currency"] == "EUR"
        assert body["auto_fetch_prices"] is False
        assert body["export_reminder_days"] == 30
        assert body["last_export_at"] is None

    def test_the_external_services_and_data_sent_are_listed(
        self, authed_client: TestClient
    ) -> None:
        services = {
            s["name"]: s for s in authed_client.get(f"{API}/settings").json()["external_services"]
        }
        assert set(services) == {"BCE", "Yahoo Finance", "OpenFIGI"}
        assert "devises" in services["BCE"]["data_sent"].lower()
        assert "ticker" in services["Yahoo Finance"]["data_sent"].lower()
        assert "isin" in services["OpenFIGI"]["data_sent"].lower()
        for service in services.values():
            assert "quantité" not in service["data_sent"].lower().replace("aucune quantité", "")

    def test_a_change_is_kept(self, authed_client: TestClient) -> None:
        settings(
            authed_client, auto_fetch_prices=True, export_reminder_days=14, reference_currency="USD"
        )
        body = authed_client.get(f"{API}/settings").json()
        assert (
            body["auto_fetch_prices"],
            body["export_reminder_days"],
            body["reference_currency"],
        ) == (
            True,
            14,
            "USD",
        )

    def test_an_empty_change_changes_nothing(self, authed_client: TestClient) -> None:
        assert settings(authed_client)["auto_fetch_prices"] is False

    @pytest.mark.parametrize(
        "patch",
        [
            {"reference_currency": "euro"},
            {"export_reminder_days": -1},
            {"auto_fetch_prices": "oui"},
        ],
    )
    def test_invalid_values_are_refused(self, authed_client: TestClient, patch: dict) -> None:
        assert authed_client.patch(f"{API}/settings", json=patch).status_code == 422


class TestManualPrices:
    def test_a_price_is_recorded_and_listed(self, authed_client: TestClient) -> None:
        etf = create_instrument(authed_client)
        created = authed_client.post(
            f"{API}/prices", json=price_input(etf["id"], "2026-01-10", "90.2")
        )
        assert created.status_code == 201, created.text
        assert created.json() == {
            **price_input(etf["id"], "2026-01-10", "90.2"),
            "source": "MANUAL",
        }
        authed_client.post(f"{API}/prices", json=price_input(etf["id"], "2026-01-05", "89"))
        listed = authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]}).json()
        assert [p["price_date"] for p in listed] == ["2026-01-05", "2026-01-10"]

    def test_the_list_can_be_narrowed_by_date(self, authed_client: TestClient) -> None:
        etf = create_instrument(authed_client)
        for on in ("2026-01-05", "2026-01-10", "2026-01-20"):
            authed_client.post(f"{API}/prices", json=price_input(etf["id"], on, "90"))
        listed = authed_client.get(
            f"{API}/prices",
            params={"instrument_id": etf["id"], "from": "2026-01-06", "to": "2026-01-15"},
        ).json()
        assert [p["price_date"] for p in listed] == ["2026-01-10"]

    def test_the_latest_entry_of_a_date_wins_in_the_valuation(
        self, authed_client: TestClient
    ) -> None:
        etf = create_instrument(authed_client)
        pea = create_account(authed_client)
        post_transaction(
            authed_client,
            account_id=pea["id"],
            type="DEPOSIT",
            trade_date="2026-01-05",
            amount="1000",
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
        authed_client.post(f"{API}/prices", json=price_input(etf["id"], "2026-01-10", "91"))
        authed_client.post(f"{API}/prices", json=price_input(etf["id"], "2026-01-10", "93"))
        body = detail(authed_client, pea["id"], "2026-01-15")
        assert body["positions"][0]["value"] == "930"
        assert body["estimated"] is False

    def test_an_old_price_still_values_the_account_but_flags_it(
        self, authed_client: TestClient
    ) -> None:
        etf = create_instrument(authed_client)
        pea = create_account(authed_client)
        post_transaction(
            authed_client,
            account_id=pea["id"],
            type="DEPOSIT",
            trade_date="2026-01-05",
            amount="1000",
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
        authed_client.post(f"{API}/prices", json=price_input(etf["id"], "2026-01-10", "91"))
        body = detail(authed_client, pea["id"], "2026-03-01")
        assert body["positions"][0]["value"] == "910" and body["estimated"] is True
        assert "price_stale" in [w["code"] for w in body["warnings"]]
        notices = summary(authed_client, "2026-03-01")["notices"]
        assert [n["kind"] for n in notices] == ["stale_price"]

    def test_unknown_instrument(self, authed_client: TestClient) -> None:
        response = authed_client.post(
            f"{API}/prices",
            json=price_input("00000000-0000-4000-8000-000000000000", "2026-01-10", "1"),
        )
        assert (
            response.status_code == 422
            and response.json()["details"][0]["field"] == "instrument_id"
        )

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_the_value_must_be_positive(self, authed_client: TestClient, value: str) -> None:
        etf = create_instrument(authed_client)
        response = authed_client.post(
            f"{API}/prices", json=price_input(etf["id"], "2026-01-10", value)
        )
        assert response.status_code == 422 and response.json()["details"][0]["field"] == "value"

    def test_a_future_date_is_refused(self, authed_client: TestClient) -> None:
        etf = create_instrument(authed_client)
        later = (date.today() + timedelta(days=2)).isoformat()
        response = authed_client.post(f"{API}/prices", json=price_input(etf["id"], later, "90"))
        assert (
            response.status_code == 422 and response.json()["details"][0]["field"] == "price_date"
        )

    @pytest.mark.parametrize(
        ("instrument", "kind", "ok"),
        [
            ({"kind": "ETF"}, "MARKET", True),
            ({"kind": "ETF"}, "NAV", False),
            ({"kind": "FUND", "name": "Fonds", "isin": None}, "NAV", True),
            ({"kind": "FUND", "name": "Fonds", "isin": None}, "MARKET", False),
            ({"kind": "SCPI", "name": "SCPI", "isin": None}, "SUBSCRIPTION", True),
            ({"kind": "SCPI", "name": "SCPI", "isin": None}, "REDEMPTION", True),
            ({"kind": "SCPI", "name": "SCPI", "isin": None}, "MARKET", False),
            ({"kind": "EURO_FUND", "name": "Euro", "isin": None}, "NAV", False),
        ],
    )
    def test_the_kind_of_price_must_suit_the_instrument(
        self, authed_client: TestClient, instrument: dict, kind: str, ok: bool
    ) -> None:
        item = create_instrument(authed_client, **instrument)
        response = authed_client.post(
            f"{API}/prices", json=price_input(item["id"], "2026-01-10", "10", kind)
        )
        assert response.status_code == (201 if ok else 422), response.text
        if not ok:
            assert response.json()["details"][0]["field"] == "kind"

    def test_the_instrument_is_required_to_list(self, authed_client: TestClient) -> None:
        assert authed_client.get(f"{API}/prices").status_code == 422


class TestScpi:
    def scenario(self, client: TestClient) -> tuple[dict, dict]:
        scpi = create_instrument(client, kind="SCPI", name="SCPI Exemple", isin=None)
        pea = create_account(client, type="CTO", name="CTO")
        post_transaction(
            client, account_id=pea["id"], type="DEPOSIT", trade_date="2026-01-05", amount="5000"
        )
        post_transaction(
            client,
            account_id=pea["id"],
            type="BUY",
            trade_date="2026-01-06",
            instrument_id=scpi["id"],
            quantity="10",
            unit_price="250",
            fees="12",
        )
        client.post(
            f"{API}/prices", json=price_input(scpi["id"], "2026-01-05", "250", "SUBSCRIPTION")
        )
        client.post(
            f"{API}/prices", json=price_input(scpi["id"], "2026-01-20", "225", "REDEMPTION")
        )
        return scpi, pea

    def test_value_at_redemption_cost_at_subscription_and_the_gap_is_visible(
        self, authed_client: TestClient
    ) -> None:
        _, pea = self.scenario(authed_client)
        position = detail(authed_client, pea["id"], "2026-01-31")["positions"][0]
        assert position["value"] == "2250" and position["total_cost"] == "2512"
        assert position["subscription_price"] == "250" and position["price"] == "225"

    def test_a_distribution_is_cash(self, authed_client: TestClient) -> None:
        scpi, pea = self.scenario(authed_client)
        post_transaction(
            authed_client,
            account_id=pea["id"],
            type="DISTRIBUTION",
            trade_date="2026-01-25",
            instrument_id=scpi["id"],
            amount="31.5",
        )
        body = detail(authed_client, pea["id"], "2026-01-31")
        assert body["cash"] == "2519.5" and body["positions"][0]["quantity"] == "10"


class TestLivretA:
    def livret(self, client: TestClient) -> dict:
        account = create_account(
            client, type="LIVRET_A", name="Livret A", institution=None, opened_on="2025-01-01"
        )
        post_transaction(
            client, account_id=account["id"], type="DEPOSIT", trade_date="2025-12-31", amount="1000"
        )
        return account

    def test_the_rate_table_starts_with_the_published_history(
        self, authed_client: TestClient
    ) -> None:
        table = authed_client.get(f"{API}/rates/livret-a").json()
        assert table[0] == {"effective_from": "2020-02-01", "value": "0.5"}
        assert {"effective_from": "2025-08-01", "value": "1.7"} in table

    def test_the_rate_table_is_dated_and_editable(self, authed_client: TestClient) -> None:
        for on, value in (("2026-02-01", "1.7"), ("2026-08-01", "2.4"), ("2026-01-01", "3")):
            created = authed_client.post(
                f"{API}/rates/livret-a", json={"effective_from": on, "value": value}
            )
            assert created.status_code == 201, created.text
            assert created.json() == {"effective_from": on, "value": value}
        authed_client.post(
            f"{API}/rates/livret-a", json={"effective_from": "2026-08-01", "value": "2.5"}
        )
        table = authed_client.get(f"{API}/rates/livret-a").json()
        assert table[-3:] == [
            {"effective_from": "2026-01-01", "value": "3"},
            {"effective_from": "2026-02-01", "value": "1.7"},
            {"effective_from": "2026-08-01", "value": "2.5"},
        ]
        assert [row["effective_from"] for row in table] == sorted(
            row["effective_from"] for row in table
        )

    @pytest.mark.parametrize("value", ["-1", "101", "0.0.1"])
    def test_a_rate_must_be_a_sensible_percentage(
        self, authed_client: TestClient, value: str
    ) -> None:
        response = authed_client.post(
            f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": value}
        )
        assert response.status_code == 422

    def test_estimated_interest_is_part_of_the_value_and_flagged(
        self, authed_client: TestClient
    ) -> None:
        account = self.livret(authed_client)
        authed_client.post(
            f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": "3"}
        )
        body = detail(authed_client, account["id"], "2026-01-31")
        assert body["value"] == "1002.5" and body["cash"] == "1000" and body["estimated"] is True
        assert summary(authed_client, "2026-01-31")["net_worth"] == "1002.5"

    def test_interest_is_credited_on_the_31st_of_december(self, authed_client: TestClient) -> None:
        account = self.livret(authed_client)
        authed_client.post(
            f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": "3"}
        )
        assert detail(authed_client, account["id"], "2026-12-31")["value"] == "1030"

    def test_real_interest_replaces_the_estimate(self, authed_client: TestClient) -> None:
        account = self.livret(authed_client)
        authed_client.post(
            f"{API}/rates/livret-a", json={"effective_from": "2026-01-01", "value": "3"}
        )
        post_transaction(
            authed_client,
            account_id=account["id"],
            type="INTEREST",
            trade_date="2026-12-31",
            amount="28.5",
        )
        assert detail(authed_client, account["id"], "2026-12-31")["value"] == "1028.5"

    def test_a_missing_rate_is_reported_as_such(self, authed_client: TestClient) -> None:
        account = create_account(
            authed_client,
            type="LIVRET_A",
            name="Vieux livret",
            institution=None,
            opened_on="2019-01-01",
        )
        post_transaction(
            authed_client,
            account_id=account["id"],
            type="DEPOSIT",
            trade_date="2019-12-31",
            amount="1000",
        )
        body = detail(authed_client, account["id"], "2020-01-31")  # avant le premier taux livré
        assert body["value"] == "1000" and body["estimated"] is True
        assert "rate_missing" in [w["code"] for w in body["warnings"]]
        assert [n["kind"] for n in summary(authed_client, "2020-01-31")["notices"]] == [
            "missing_rate"
        ]

    def test_the_cap_still_applies_to_the_cash_balance(self, authed_client: TestClient) -> None:
        account = self.livret(authed_client)
        usage = detail(authed_client, account["id"], "2026-01-31")["deposit_cap_usage"]
        assert usage["deposited"] == "1000" and usage["cap"] == "22950"


class TestRefresh:
    def etf(self, client: TestClient, **overrides: object) -> dict:
        return create_instrument(client, price_ticker="CW8.PA", **overrides)

    def test_nothing_leaves_while_automatic_retrieval_is_off(
        self, authed_client: TestClient
    ) -> None:
        providers = install(authed_client, prices=FakePrices({"CW8.PA": [(recent(), "90")]}))
        self.etf(authed_client)
        body = authed_client.post(f"{API}/prices/refresh").json()
        assert [(s["source"], s["status"]) for s in body["sources"]] == [
            ("ecb", "disabled"),
            ("yahoo", "disabled"),
        ]
        assert providers.prices.calls == [] and providers.rates.calls == 0  # type: ignore[attr-defined]

    def test_prices_are_fetched_stored_and_not_duplicated(self, authed_client: TestClient) -> None:
        yesterday = recent()
        providers = install(
            authed_client, prices=FakePrices({"CW8.PA": [(recent(2), "89"), (yesterday, "90")]})
        )
        etf = self.etf(authed_client)
        settings(authed_client, auto_fetch_prices=True)

        first = authed_client.post(f"{API}/prices/refresh").json()
        yahoo = next(s for s in first["sources"] if s["source"] == "yahoo")
        assert (yahoo["status"], yahoo["updated"]) == ("ok", 2)
        stored = authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]}).json()
        assert [(p["price_date"], p["value"], p["source"]) for p in stored] == [
            (recent(2).isoformat(), "89", "PROVIDER"),
            (yesterday.isoformat(), "90", "PROVIDER"),
        ]

        second = authed_client.post(f"{API}/prices/refresh").json()
        assert next(s for s in second["sources"] if s["source"] == "yahoo")["updated"] == 0
        assert (
            len(authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]}).json()) == 2
        )
        # Seuls le ticker et une période grossière sont envoyés, plus courte la deuxième fois.
        assert providers.prices.calls == [(["CW8.PA"], "max"), (["CW8.PA"], "5d")]  # type: ignore[attr-defined]

    def test_only_instruments_with_a_ticker_in_automatic_mode_are_sent(
        self, authed_client: TestClient
    ) -> None:
        providers = install(authed_client, prices=FakePrices({"CW8.PA": [(recent(), "90")]}))
        self.etf(authed_client)
        create_instrument(authed_client, name="Sans ticker", isin="FR0000000028")
        create_instrument(
            authed_client,
            name="Manuel",
            isin="FR0000000036",
            price_ticker="MAN.PA",
            price_mode="MANUAL",
        )
        create_instrument(
            authed_client, kind="SCPI", name="SCPI", isin=None, price_ticker="SCPI.PA"
        )
        settings(authed_client, auto_fetch_prices=True)
        authed_client.post(f"{API}/prices/refresh")
        assert providers.prices.calls == [(["CW8.PA"], "max")]  # type: ignore[attr-defined]

    def test_a_manual_price_of_the_same_day_is_not_overridden(
        self, authed_client: TestClient
    ) -> None:
        day = recent()
        install(authed_client, prices=FakePrices({"CW8.PA": [(day, "90")]}))
        etf = self.etf(authed_client)
        authed_client.post(f"{API}/prices", json=price_input(etf["id"], day.isoformat(), "95"))
        settings(authed_client, auto_fetch_prices=True)
        authed_client.post(f"{API}/prices/refresh")
        stored = authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]}).json()
        assert [(p["value"], p["source"]) for p in stored] == [("95", "MANUAL")]

    def test_a_failing_source_changes_nothing_and_does_not_block_the_other(
        self, authed_client: TestClient
    ) -> None:
        rates = FakeRates([FetchedRate("USD", date(2026, 1, 6), Decimal("1.1725"))])
        install(authed_client, rates=rates, prices=FakePrices(error="Yahoo Finance indisponible"))
        etf = self.etf(authed_client, currency="USD")
        authed_client.post(
            f"{API}/prices", json=price_input(etf["id"], "2026-01-02", "100", currency="USD")
        )
        settings(authed_client, auto_fetch_prices=True)
        sources = {
            s["source"]: s for s in authed_client.post(f"{API}/prices/refresh").json()["sources"]
        }
        assert (
            sources["yahoo"]["status"] == "failed" and "indisponible" in sources["yahoo"]["message"]
        )
        assert sources["ecb"]["status"] == "ok" and sources["ecb"]["updated"] == 1
        assert (
            len(authed_client.get(f"{API}/prices", params={"instrument_id": etf["id"]}).json()) == 1
        )

    def test_missing_tickers_make_the_result_partial(self, authed_client: TestClient) -> None:
        install(authed_client, prices=FakePrices({"CW8.PA": [(recent(), "90")]}, failed=["BAD.PA"]))
        self.etf(authed_client)
        create_instrument(authed_client, name="Autre", isin="FR0000000028", price_ticker="BAD.PA")
        settings(authed_client, auto_fetch_prices=True)
        yahoo = next(
            s
            for s in authed_client.post(f"{API}/prices/refresh").json()["sources"]
            if s["source"] == "yahoo"
        )
        assert (yahoo["status"], yahoo["updated"]) == ("partial", 1)
        assert "BAD.PA" in yahoo["message"]

    def test_no_foreign_currency_means_no_request_to_the_central_bank(
        self, authed_client: TestClient
    ) -> None:
        providers = install(authed_client)
        create_account(authed_client)
        settings(authed_client, auto_fetch_prices=True)
        ecb = next(
            s
            for s in authed_client.post(f"{API}/prices/refresh").json()["sources"]
            if s["source"] == "ecb"
        )
        assert (ecb["status"], ecb["updated"]) == ("ok", 0) and providers.rates.calls == 0  # type: ignore[attr-defined]

    def test_only_the_currencies_in_use_are_stored_and_not_twice(
        self, authed_client: TestClient
    ) -> None:
        rates = FakeRates(
            [
                FetchedRate("USD", date(2026, 1, 6), Decimal("1.1725")),
                FetchedRate("USD", date(2026, 1, 5), Decimal("1.17")),
                FetchedRate("GBP", date(2026, 1, 6), Decimal("0.8701")),
            ]
        )
        install(authed_client, rates=rates)
        create_instrument(authed_client, currency="USD")
        settings(authed_client, auto_fetch_prices=True)
        first = next(
            s
            for s in authed_client.post(f"{API}/prices/refresh").json()["sources"]
            if s["source"] == "ecb"
        )
        second = next(
            s
            for s in authed_client.post(f"{API}/prices/refresh").json()["sources"]
            if s["source"] == "ecb"
        )
        assert first["updated"] == 2 and second["updated"] == 0

    def test_fetched_rates_convert_a_foreign_position(self, authed_client: TestClient) -> None:
        rates = FakeRates([FetchedRate("USD", date(2026, 1, 6), Decimal("1.1725"))])
        install(authed_client, rates=rates)
        etf = create_instrument(authed_client, currency="USD", name="ETF US", isin="FR0000000028")
        pea = create_account(authed_client)
        post_transaction(
            authed_client,
            account_id=pea["id"],
            type="DEPOSIT",
            trade_date="2026-01-02",
            amount="2000",
        )
        post_transaction(
            authed_client,
            account_id=pea["id"],
            type="BUY",
            trade_date="2026-01-03",
            instrument_id=etf["id"],
            quantity="10",
            unit_price="85",
        )
        authed_client.post(
            f"{API}/prices", json=price_input(etf["id"], "2026-01-06", "117.25", currency="USD")
        )

        before = detail(authed_client, pea["id"], "2026-01-06")
        assert (
            before["positions"][0]["value"] is None
        )  # non convertible tant qu'aucun taux n'est connu
        assert "non_convertible" in [w["code"] for w in before["warnings"]]
        assert [n["kind"] for n in summary(authed_client, "2026-01-06")["notices"]] == [
            "missing_fx"
        ]

        settings(authed_client, auto_fetch_prices=True)
        authed_client.post(f"{API}/prices/refresh")
        after = detail(authed_client, pea["id"], "2026-01-06")
        assert after["positions"][0]["value"] == "1000"  # 10 x 117,25 USD / 1,1725
        assert after["estimated"] is False
        assert summary(authed_client, "2026-01-06")["net_worth"] == "2150"  # 1150 + 1000


class TestTickerSuggestions:
    def test_refused_while_automatic_retrieval_is_off(self, authed_client: TestClient) -> None:
        providers = install(authed_client)
        etf = create_instrument(authed_client)
        response = authed_client.post(f"{API}/instruments/{etf['id']}/ticker-suggestions")
        assert response.status_code == 409
        assert providers.tickers.calls == []  # type: ignore[attr-defined]

    def test_only_the_isin_is_sent(self, authed_client: TestClient) -> None:
        providers = install(authed_client)
        etf = create_instrument(authed_client)
        settings(authed_client, auto_fetch_prices=True)
        response = authed_client.post(f"{API}/instruments/{etf['id']}/ticker-suggestions")
        assert response.status_code == 200
        assert response.json() == [
            {"ticker": "CW8.PA", "exchange": "FP", "name": "AMUNDI MSCI WORLD"}
        ]
        assert providers.tickers.calls == ["IE00B4L5Y983"]  # type: ignore[attr-defined]

    def test_an_instrument_without_isin(self, authed_client: TestClient) -> None:
        install(authed_client)
        item = create_instrument(authed_client, isin=None)
        settings(authed_client, auto_fetch_prices=True)
        assert (
            authed_client.post(f"{API}/instruments/{item['id']}/ticker-suggestions").status_code
            == 422
        )

    def test_unknown_instrument(self, authed_client: TestClient) -> None:
        install(authed_client)
        settings(authed_client, auto_fetch_prices=True)
        url = f"{API}/instruments/00000000-0000-4000-8000-000000000000/ticker-suggestions"
        assert authed_client.post(url).status_code == 404

    def test_a_service_failure_is_a_bad_gateway_with_a_message(
        self, authed_client: TestClient
    ) -> None:
        install(authed_client, tickers=FakeTickers(error="OpenFIGI indisponible"))
        etf = create_instrument(authed_client)
        settings(authed_client, auto_fetch_prices=True)
        response = authed_client.post(f"{API}/instruments/{etf['id']}/ticker-suggestions")
        assert response.status_code == 502
        assert response.json()["code"] == "external_source_failed"
        assert "OpenFIGI" in response.json()["message"]
