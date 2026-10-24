"""export-format.md, règles de restauration : instance vide, version connue, tout ou rien."""

import copy
from pathlib import Path

from fastapi.testclient import TestClient

from tests.api_helpers import API, create_account
from tests.data_helpers import fresh_client, populate

MINIMAL = {
    "format_version": 1,
    "exported_at": "2026-10-24T12:00:00Z",
    "reference_currency": "EUR",
    "settings": {"auto_fetch_prices": False, "export_reminder_days": 30},
    "accounts": [],
    "instruments": [],
    "transactions": [],
    "prices": [],
    "declared_balances": [],
    "rates": [],
    "imports": [],
    "import_mappings": [],
}
ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
INSTRUMENT_ID = "22222222-2222-4222-8222-222222222222"
TRANSACTION_ID = "33333333-3333-4333-8333-333333333333"


def payload(**changes: object) -> dict:
    body = copy.deepcopy(MINIMAL)
    body.update(changes)
    return body


def account(**changes: object) -> dict:
    return {
        "id": ACCOUNT_ID,
        "type": "PEA",
        "name": "PEA",
        "institution": None,
        "currency": "EUR",
        "opened_on": "2026-01-02",
        "closed_on": None,
        "settings": {"deposit_cap": "150000"},
        **changes,
    }


def transaction(**changes: object) -> dict:
    version = {
        "version": 1,
        "voided": False,
        "type": "DEPOSIT",
        "trade_date": "2026-01-05",
        "instrument_id": None,
        "quantity": None,
        "unit_price": None,
        "fees": "0",
        "cash_amount": "1000",
        "currency": "EUR",
        "unlock_date": None,
        "transfer_group_id": None,
        "label": "",
        "external_id": None,
        "line_fingerprint": None,
        "import_id": None,
        "created_at": "2026-01-05T10:00:00Z",
    }
    return {
        "id": TRANSACTION_ID,
        "account_id": ACCOUNT_ID,
        "created_at": "2026-01-05T10:00:00Z",
        "versions": [version],
        **changes,
    }


def problems(response) -> list[str]:  # type: ignore[no-untyped-def]
    assert response.status_code == 422, response.text
    return [f"{d['field']}: {d['message']}" for d in response.json()["details"]]


def test_a_minimal_valid_file_is_accepted(authed_client: TestClient) -> None:
    assert authed_client.post(f"{API}/data/restore", json=MINIMAL).status_code == 204


def test_only_an_empty_instance_accepts_a_restore(authed_client: TestClient) -> None:
    create_account(authed_client)
    response = authed_client.post(f"{API}/data/restore", json=payload(accounts=[account()]))
    assert response.status_code == 409
    assert [a["name"] for a in authed_client.get(f"{API}/accounts").json()] == ["PEA Courtier A"]


def test_a_second_restore_is_refused(authed_client: TestClient) -> None:
    assert (
        authed_client.post(f"{API}/data/restore", json=payload(accounts=[account()])).status_code
        == 204
    )
    assert (
        authed_client.post(f"{API}/data/restore", json=payload(accounts=[account()])).status_code
        == 409
    )


def test_an_instance_with_assets_but_no_account_is_not_empty(authed_client: TestClient) -> None:
    from tests.api_helpers import create_instrument

    create_instrument(authed_client)
    assert authed_client.post(f"{API}/data/restore", json=MINIMAL).status_code == 409


def test_a_newer_format_version_is_refused_with_a_clear_message(authed_client: TestClient) -> None:
    found = problems(authed_client.post(f"{API}/data/restore", json=payload(format_version=2)))
    assert any("format_version" in p and "version" in p.lower() for p in found)
    assert any("mettez" in p.lower() or "récente" in p.lower() for p in found)


def test_a_missing_or_malformed_version_is_refused(authed_client: TestClient) -> None:
    for bad in (None, "1", 0, True):
        body = payload(format_version=bad)
        assert problems(authed_client.post(f"{API}/data/restore", json=body))
    missing = payload()
    del missing["format_version"]
    assert problems(authed_client.post(f"{API}/data/restore", json=missing))


def test_a_file_that_is_not_an_export_is_refused(authed_client: TestClient) -> None:
    assert authed_client.post(f"{API}/data/restore", json=[1, 2]).status_code == 422
    assert problems(authed_client.post(f"{API}/data/restore", json={"format_version": 1}))


def test_everything_is_validated_before_anything_is_written(authed_client: TestClient) -> None:
    body = payload(
        accounts=[
            account(),
            account(id="44444444-4444-4444-8444-444444444444", name="Autre", type="NOPE"),
        ],
        transactions=[transaction(account_id="99999999-9999-4999-8999-999999999999")],
    )
    found = problems(authed_client.post(f"{API}/data/restore", json=body))
    assert any(p.startswith("accounts[1].type") for p in found)
    assert any(p.startswith("transactions[0].account_id") for p in found)
    assert authed_client.get(f"{API}/accounts").json() == []  # rien n'a été écrit


def test_invalid_decimals_dates_and_currencies_are_listed(authed_client: TestClient) -> None:
    bad = transaction()
    bad["versions"][0].update(cash_amount="beaucoup", trade_date="31/02/2026", currency="eur")
    found = problems(
        authed_client.post(
            f"{API}/data/restore", json=payload(accounts=[account()], transactions=[bad])
        )
    )
    joined = " | ".join(found)
    assert "cash_amount" in joined and "trade_date" in joined and "currency" in joined


def test_dangling_references_are_found(authed_client: TestClient) -> None:
    bad = transaction()
    bad["versions"][0].update(
        type="BUY", instrument_id=INSTRUMENT_ID, quantity="1", unit_price="1", import_id="x"
    )
    found = problems(
        authed_client.post(
            f"{API}/data/restore", json=payload(accounts=[account()], transactions=[bad])
        )
    )
    joined = " | ".join(found)
    assert "instrument_id" in joined and "import_id" in joined


def test_duplicate_identifiers_are_refused(authed_client: TestClient) -> None:
    found = problems(
        authed_client.post(f"{API}/data/restore", json=payload(accounts=[account(), account()]))
    )
    assert any("accounts[1].id" in p for p in found)


def test_the_number_of_listed_problems_is_bounded(authed_client: TestClient) -> None:
    many = [
        account(id=f"{i:08d}-0000-4000-8000-000000000000", type="NOPE", name=str(i))
        for i in range(200)
    ]
    assert (
        len(problems(authed_client.post(f"{API}/data/restore", json=payload(accounts=many)))) <= 50
    )


def test_restoring_on_a_second_instance_leaves_the_first_untouched(
    authed_client: TestClient, tmp_path: Path
) -> None:
    populate(authed_client)
    exported = authed_client.get(f"{API}/data/export").json()
    before = authed_client.get(f"{API}/accounts", params={"include_closed": "true"}).json()
    with fresh_client(tmp_path) as other:
        assert other.post(f"{API}/data/restore", json=exported).status_code == 204
    assert authed_client.get(f"{API}/accounts", params={"include_closed": "true"}).json() == before
