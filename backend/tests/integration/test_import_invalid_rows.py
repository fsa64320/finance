"""FR-017 : lignes invalides listées avec leur cause, rien d'écrit sans confirmation."""

from fastapi.testclient import TestClient

from finance.services.imports import MAX_FILE_BYTES, PreviewStore
from tests.api_helpers import API, create_account
from tests.import_helpers import (
    ETF_ISIN,
    commit,
    csv_bytes,
    fixture,
    instruments,
    preview,
    resolutions,
    transactions,
)


def setup(client: TestClient, content: bytes) -> tuple[str, dict]:
    account_id = create_account(client, opened_on="2023-12-01")["id"]
    return account_id, preview(client, account_id, content).json()


def test_les_lignes_invalides_sont_listees_avec_leur_cause(authed_client: TestClient) -> None:
    _, body = setup(authed_client, fixture("lignes_invalides.csv"))
    assert body["rows_valid"] == 2
    reasons = {item["line"]: item["reason"] for item in body["rows_rejected"]}
    assert sorted(reasons) == [3, 4, 5, 6]
    assert "31/02/2024" in reasons[3]
    assert "Montant manquant" in reasons[4]
    assert "Spéculation" in reasons[5]
    assert "abc" in reasons[6]


def test_rien_n_est_ecrit_sans_confirmation(authed_client: TestClient) -> None:
    account_id, body = setup(authed_client, fixture("lignes_invalides.csv"))
    refused = commit(
        authed_client,
        body["preview_id"],
        confirm_rejected=False,
        instrument_resolutions=resolutions(body, {}),
    )
    assert refused.status_code == 422
    assert refused.json()["details"][0]["field"] == "confirm_rejected"
    assert transactions(authed_client, account_id) == []
    assert instruments(authed_client) == []


def test_import_partiel_confirme(authed_client: TestClient) -> None:
    account_id, body = setup(authed_client, fixture("lignes_invalides.csv"))
    done = commit(
        authed_client,
        body["preview_id"],
        confirm_rejected=True,
        instrument_resolutions=resolutions(body, {ETF_ISIN: "ETF"}),
    )
    assert done.status_code == 201, done.text
    assert (done.json()["rows_added"], done.json()["rows_rejected"]) == (2, 4)
    assert len(transactions(authed_client, account_id)) == 2


def test_une_regle_metier_rejette_la_ligne_avec_sa_cause(authed_client: TestClient) -> None:
    content = csv_bytes(
        "03/01/2024;Versement;Versement espèces;;;;100,00;;",
        "03/01/2020;Versement;Avant l'ouverture;;;;100,00;;",
        "04/01/2024;Frais;Frais négatifs;;;;0,00;;",
    )
    _, body = setup(authed_client, content)
    assert body["rows_valid"] == 1
    reasons = {item["line"]: item["reason"] for item in body["rows_rejected"]}
    assert "ouverture" in reasons[3]
    assert 4 in reasons


def test_fichier_trop_volumineux(authed_client: TestClient) -> None:
    account_id = create_account(authed_client)["id"]
    response = preview(authed_client, account_id, b"x" * (MAX_FILE_BYTES + 1))
    assert response.status_code == 422
    assert "volumineux" in response.json()["message"] or "volumineux" in str(
        response.json().get("details")
    )


def test_fichier_vide(authed_client: TestClient) -> None:
    account_id = create_account(authed_client)["id"]
    response = preview(authed_client, account_id, fixture("vide.csv"))
    assert response.status_code == 422
    assert "vide" in str(response.json())


def test_encodage_incompatible(authed_client: TestClient) -> None:
    account_id = create_account(authed_client)["id"]
    response = preview(
        authed_client, account_id, fixture("courtier_a_50_lignes.csv"), encoding="utf-8"
    )
    assert response.status_code == 422
    assert "encodage" in str(response.json())


def test_colonne_declaree_introuvable(authed_client: TestClient) -> None:
    account_id = create_account(authed_client)["id"]
    response = preview(
        authed_client,
        account_id,
        fixture("courtier_a_50_lignes.csv"),
        columns={"trade_date": "Date", "type": "Colonne absente"},
    )
    assert response.status_code == 422
    assert "Colonne absente" in str(response.json())


def test_compte_introuvable(authed_client: TestClient) -> None:
    response = preview(
        authed_client, "00000000-0000-4000-8000-000000000000", fixture("courtier_a_50_lignes.csv")
    )
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "account_id"


def test_apercu_inconnu(authed_client: TestClient) -> None:
    assert commit(authed_client, "inconnu").status_code == 404


def test_un_apercu_se_valide_une_seule_fois(authed_client: TestClient) -> None:
    _, body = setup(authed_client, csv_bytes("03/01/2024;Versement;Versement espèces;;;;100,00;;"))
    assert commit(authed_client, body["preview_id"]).status_code == 201
    assert commit(authed_client, body["preview_id"]).status_code == 404


def test_session_exigee(authed_client: TestClient) -> None:
    authed_client.cookies.clear()
    assert authed_client.post(f"{API}/imports/commit", json={}).status_code == 401


class TestPreviewStore:
    def test_un_apercu_expire(self) -> None:
        now = [1000.0]
        store = PreviewStore(ttl_seconds=60, clock=lambda: now[0])
        token = store.put("contenu")
        assert store.get(token) == "contenu"
        now[0] += 61
        assert store.get(token) is None

    def test_les_plus_anciens_sont_oublies(self) -> None:
        store = PreviewStore(ttl_seconds=60, clock=lambda: 0.0, capacity=2)
        first, second, third = store.put("a"), store.put("b"), store.put("c")
        assert store.get(first) is None
        assert store.get(second) == "b" and store.get(third) == "c"

    def test_retrait(self) -> None:
        store = PreviewStore(ttl_seconds=60, clock=lambda: 0.0)
        token = store.put("x")
        store.discard(token)
        assert store.get(token) is None
