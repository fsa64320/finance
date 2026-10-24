"""Clarification 4, FR-016 : actifs inconnus à créer, rattacher ou ignorer, après validation."""

from fastapi.testclient import TestClient

from tests.api_helpers import create_account, create_instrument
from tests.import_helpers import commit, fixture, instruments, preview, transactions

ALPHA = "FR0000000036"


def setup(client: TestClient) -> tuple[str, dict]:
    account_id = create_account(client, opened_on="2023-12-01")["id"]
    body = preview(client, account_id, fixture("actifs_inconnus.csv")).json()
    return account_id, body


def keyed(body: dict) -> dict[str, str]:
    return {(item["isin"] or item["name"]): item["key"] for item in body["unknown_instruments"]}


def test_les_actifs_inconnus_sont_listes_avec_les_informations_du_fichier(
    authed_client: TestClient,
) -> None:
    _, body = setup(authed_client)
    assert body["rows_valid"] == 4
    listed = {item["name"]: item for item in body["unknown_instruments"]}
    assert set(listed) == {"Fonds Inconnu Alpha", "Fonds Inconnu Beta"}
    assert listed["Fonds Inconnu Alpha"]["isin"] == ALPHA
    assert listed["Fonds Inconnu Alpha"]["rows"] == 2
    assert listed["Fonds Inconnu Beta"]["isin"] is None
    assert listed["Fonds Inconnu Beta"]["rows"] == 1
    assert len({item["key"] for item in body["unknown_instruments"]}) == 2


def test_rien_n_est_cree_avant_la_validation(authed_client: TestClient) -> None:
    account_id, _ = setup(authed_client)
    assert instruments(authed_client) == []
    assert transactions(authed_client, account_id) == []


def test_creer_les_deux_actifs(authed_client: TestClient) -> None:
    account_id, body = setup(authed_client)
    keys = keyed(body)
    done = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[
            {"key": keys[ALPHA], "action": "create", "kind": "FUND"},
            {"key": keys["Fonds Inconnu Beta"], "action": "create", "kind": "FCPE"},
        ],
    )
    assert done.status_code == 201, done.text
    assert done.json()["instruments_created"] == 2
    assert done.json()["rows_added"] == 4
    created = {item["name"]: item for item in instruments(authed_client)}
    assert created["Fonds Inconnu Alpha"]["isin"] == ALPHA
    assert created["Fonds Inconnu Alpha"]["kind"] == "FUND"
    assert created["Fonds Inconnu Beta"]["kind"] == "FCPE"
    assert created["Fonds Inconnu Beta"]["currency"] == "EUR"
    assert len(transactions(authed_client, account_id)) == 4


def test_rattacher_a_un_actif_existant(authed_client: TestClient) -> None:
    account_id, body = setup(authed_client)
    existing = create_instrument(authed_client, isin="IE00B4L5Y983", name="ETF Monde")
    keys = keyed(body)
    done = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[
            {"key": keys[ALPHA], "action": "link", "instrument_id": existing["id"]},
            {"key": keys["Fonds Inconnu Beta"], "action": "link", "instrument_id": existing["id"]},
        ],
    )
    assert done.status_code == 201, done.text
    assert done.json()["instruments_created"] == 0
    assert len(instruments(authed_client)) == 1
    bought = [t for t in transactions(authed_client, account_id) if t["type"] == "BUY"]
    assert {t["instrument_id"] for t in bought} == {existing["id"]}


def test_ignorer_les_lignes_d_un_actif(authed_client: TestClient) -> None:
    account_id, body = setup(authed_client)
    keys = keyed(body)
    done = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[
            {"key": keys[ALPHA], "action": "skip"},
            {"key": keys["Fonds Inconnu Beta"], "action": "create", "kind": "FUND"},
        ],
    )
    assert done.status_code == 201, done.text
    assert (done.json()["rows_added"], done.json()["rows_skipped"]) == (2, 2)
    assert [item["name"] for item in instruments(authed_client)] == ["Fonds Inconnu Beta"]
    assert len(transactions(authed_client, account_id)) == 2


def test_un_actif_sans_decision_bloque_la_validation_et_rien_n_est_ecrit(
    authed_client: TestClient,
) -> None:
    account_id, body = setup(authed_client)
    keys = keyed(body)
    done = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[{"key": keys[ALPHA], "action": "create", "kind": "FUND"}],
    )
    assert done.status_code == 422
    assert done.json()["details"][0]["field"] == "instrument_resolutions"
    assert "Fonds Inconnu Beta" in done.json()["details"][0]["message"]
    assert instruments(authed_client) == []
    assert transactions(authed_client, account_id) == []


def test_creer_sans_type_ou_rattacher_a_un_actif_introuvable(authed_client: TestClient) -> None:
    _, body = setup(authed_client)
    keys = keyed(body)
    no_kind = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[
            {"key": keys[ALPHA], "action": "create"},
            {"key": keys["Fonds Inconnu Beta"], "action": "skip"},
        ],
    )
    assert no_kind.status_code == 422
    missing = commit(
        authed_client,
        body["preview_id"],
        instrument_resolutions=[
            {
                "key": keys[ALPHA],
                "action": "link",
                "instrument_id": "00000000-0000-4000-8000-000000000000",
            },
            {"key": keys["Fonds Inconnu Beta"], "action": "skip"},
        ],
    )
    assert missing.status_code == 422
    assert instruments(authed_client) == []


def test_un_actif_deja_connu_n_est_pas_signale(authed_client: TestClient) -> None:
    account_id = create_account(authed_client, opened_on="2023-12-01")["id"]
    create_instrument(authed_client, isin=ALPHA, name="Nom différent dans l'application")
    create_instrument(authed_client, isin=None, name="fonds inconnu beta")
    body = preview(authed_client, account_id, fixture("actifs_inconnus.csv")).json()
    assert body["unknown_instruments"] == []
    done = commit(authed_client, body["preview_id"])
    assert done.status_code == 201, done.text
    assert done.json()["rows_added"] == 4
