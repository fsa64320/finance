"""FR-029, SC-008 : sources de prix simulées ; seuls tickers, ISIN et devises sortent, et rien ne
sort tant que la récupération automatique n'est pas activée."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from finance.prices.base import FetchedPrice, ProviderError
from finance.prices.ecb import ECB_URL, EcbRates
from finance.prices.openfigi import OPENFIGI_URL, OpenFigi
from finance.prices.yahoo import YahooPrices

XML = (Path(__file__).parent.parent / "fixtures" / "providers" / "ecb_hist_90d.xml").read_bytes()


def client(handler):  # type: ignore[no-untyped-def]
    return httpx.Client(transport=httpx.MockTransport(handler))


class TestEcb:
    def test_reads_the_reference_rates_of_every_published_day(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=XML)

        rates = EcbRates(client(handler)).fetch()
        assert {(r.quote, r.rate_date.isoformat(), r.value) for r in rates} == {
            ("USD", "2026-01-06", Decimal("1.1725")),
            ("GBP", "2026-01-06", Decimal("0.8701")),
            ("JPY", "2026-01-06", Decimal("183.20")),
            ("USD", "2026-01-05", Decimal("1.1700")),
            ("GBP", "2026-01-05", Decimal("0.8690")),
        }
        assert all(isinstance(r.value, Decimal) for r in rates)

    def test_the_request_carries_nothing_about_the_user(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, content=XML)

        EcbRates(client(handler)).fetch()
        (request,) = seen
        assert request.method == "GET" and str(request.url) == ECB_URL
        assert request.url.query == b"" and request.content == b""
        assert "cookie" not in request.headers and "authorization" not in request.headers

    @pytest.mark.parametrize("status", [404, 500, 503])
    def test_an_unavailable_source_is_a_provider_error(self, status: int) -> None:
        with pytest.raises(ProviderError, match="BCE"):
            EcbRates(client(lambda r: httpx.Response(status))).fetch()

    def test_a_network_failure_is_a_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("réseau coupé")

        with pytest.raises(ProviderError, match="BCE"):
            EcbRates(client(handler)).fetch()

    def test_an_unreadable_answer_is_a_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="BCE"):
            EcbRates(client(lambda r: httpx.Response(200, content=b"<html>pas du XML"))).fetch()

    def test_a_document_declaring_entities_is_refused(self) -> None:
        bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
        with pytest.raises(ProviderError, match="BCE"):
            EcbRates(client(lambda r: httpx.Response(200, content=bomb))).fetch()

    def test_malformed_rates_are_skipped(self) -> None:
        body = XML.replace(b'rate="1.1725"', b'rate="pas un nombre"')
        rates = EcbRates(client(lambda r: httpx.Response(200, content=body))).fetch()
        assert ("USD", "2026-01-06") not in {(r.quote, r.rate_date.isoformat()) for r in rates}
        assert len(rates) == 4


class TestYahoo:
    def test_returns_the_prices_found_per_ticker(self) -> None:
        def download(ticker: str, period: str):  # type: ignore[no-untyped-def]
            return [(date(2026, 1, 5), Decimal("90.1")), (date(2026, 1, 6), Decimal("91.2"))], "EUR"

        batch = YahooPrices(download).fetch(["CW8.PA"], period="1mo")
        assert batch.failed == []
        assert batch.found["CW8.PA"] == [
            FetchedPrice("CW8.PA", date(2026, 1, 5), Decimal("90.1"), "EUR"),
            FetchedPrice("CW8.PA", date(2026, 1, 6), Decimal("91.2"), "EUR"),
        ]

    def test_only_the_ticker_and_a_coarse_period_are_sent(self) -> None:
        calls: list[tuple[object, ...]] = []

        def download(*args: object):  # type: ignore[no-untyped-def]
            calls.append(args)
            return [], "EUR"

        YahooPrices(download).fetch(["CW8.PA", "AIR.PA"], period="5d")  # type: ignore[arg-type]
        assert calls == [("CW8.PA", "5d"), ("AIR.PA", "5d")]

    def test_pence_are_converted_to_pounds(self) -> None:
        def download(ticker: str, period: str):  # type: ignore[no-untyped-def]
            return [(date(2026, 1, 5), Decimal("1250"))], "GBp"

        batch = YahooPrices(download).fetch(["VUSA.L"], period="1mo")
        assert batch.found["VUSA.L"] == [
            FetchedPrice("VUSA.L", date(2026, 1, 5), Decimal("12.5"), "GBP")
        ]

    def test_a_failing_ticker_is_reported_and_the_others_kept(self) -> None:
        def download(ticker: str, period: str):  # type: ignore[no-untyped-def]
            if ticker == "BAD":
                raise RuntimeError("blocage de la source")
            return [(date(2026, 1, 5), Decimal("10"))], "EUR"

        batch = YahooPrices(download).fetch(["OK.PA", "BAD"], period="1mo")
        assert set(batch.found) == {"OK.PA"} and batch.failed == ["BAD"]

    def test_a_ticker_without_data_is_reported_as_failed(self) -> None:
        batch = YahooPrices(lambda t, p: ([], "EUR")).fetch(["NONE"], period="1mo")
        assert batch.found == {} and batch.failed == ["NONE"]

    def test_the_source_can_be_switched_off(self) -> None:
        def download(ticker: str, period: str):  # type: ignore[no-untyped-def]
            raise AssertionError("aucune requête ne doit partir")

        with pytest.raises(ProviderError, match="désactiv"):
            YahooPrices(download, enabled=False).fetch(["CW8.PA"], period="1mo")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


FIGI_ANSWER = [
    {
        "data": [
            {
                "ticker": "CW8",
                "exchCode": "FP",
                "name": "AMUNDI MSCI WORLD",
                "marketSector": "Equity",
            },
            {
                "ticker": "CW8",
                "exchCode": "FP",
                "name": "AMUNDI MSCI WORLD",
                "marketSector": "Equity",
            },
            {
                "ticker": "MWRD",
                "exchCode": "LN",
                "name": "AMUNDI MSCI WORLD",
                "marketSector": "Equity",
            },
            {"ticker": "XYZ", "exchCode": "US", "name": "UN FUTURE", "marketSector": "Comdty"},
        ]
    }
]


class TestOpenFigi:
    def test_suggests_tickers_in_the_form_the_price_source_expects(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=FIGI_ANSWER)

        suggestions = OpenFigi(client(handler)).suggest("LU1681043599")
        assert [(s.ticker, s.exchange, s.name) for s in suggestions] == [
            ("CW8.PA", "FP", "AMUNDI MSCI WORLD"),
            ("MWRD.L", "LN", "AMUNDI MSCI WORLD"),
        ]

    def test_only_the_isin_is_sent(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[{"warning": "No identifier found."}])

        assert OpenFigi(client(handler)).suggest("LU1681043599") == []
        (request,) = seen
        assert request.method == "POST" and str(request.url) == OPENFIGI_URL
        assert json.loads(request.content) == [{"idType": "ID_ISIN", "idValue": "LU1681043599"}]
        assert "cookie" not in request.headers and "authorization" not in request.headers

    def test_the_rate_limit_of_25_requests_a_minute_is_respected(self) -> None:
        clock = FakeClock()
        figi = OpenFigi(client(lambda r: httpx.Response(200, json=FIGI_ANSWER)), clock=clock)
        for _ in range(25):
            figi.suggest("LU1681043599")
        with pytest.raises(ProviderError, match="minute"):
            figi.suggest("LU1681043599")
        clock.now += 61
        assert figi.suggest("LU1681043599")

    def test_the_services_own_limit_is_a_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="OpenFIGI"):
            OpenFigi(client(lambda r: httpx.Response(429))).suggest("LU1681043599")

    def test_a_failure_is_a_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="OpenFIGI"):
            OpenFigi(client(lambda r: httpx.Response(500))).suggest("LU1681043599")

    def test_an_invalid_isin_never_leaves(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("aucune requête ne doit partir")

        with pytest.raises(ProviderError, match="ISIN"):
            OpenFigi(client(handler)).suggest("pas un isin")
