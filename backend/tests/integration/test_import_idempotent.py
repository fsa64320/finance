"""FR-018, SC-003 : réimportation sans doublon ; 500 lignes en moins d'une minute."""

import time

from fastapi.testclient import TestClient

from tests.api_helpers import API, create_account, create_instrument
from tests.import_helpers import (
    ACTION_ISIN,
    COLUMNS,
    ETF_ISIN,
    commit,
    csv_bytes,
    fixture,
    import_all,
    preview,
    transactions,
)

KINDS = {ETF_ISIN: "ETF", ACTION_ISIN: "EQUITY"}


def pea(client: TestClient) -> str:
    return create_account(client, opened_on="2023-12-01")["id"]  # type: ignore[no-any-return]


def test_cinquante_lignes_importees_puis_reimportees(authed_client: TestClient) -> None:
    account_id = pea(authed_client)
    content = fixture("courtier_a_50_lignes.csv")

    first = import_all(authed_client, account_id, content, KINDS)
    assert (first["rows_added"], first["rows_skipped"], first["rows_rejected"]) == (50, 0, 0)
    assert first["instruments_created"] == 2
    assert len(transactions(authed_client, account_id)) == 50

    again = preview(authed_client, account_id, content).json()
    assert again["rows_valid"] == 0
    assert again["rows_duplicate"] == 50
    assert again["unknown_instruments"] == []  # les actifs créés sont reconnus par leur ISIN
    second = commit(authed_client, again["preview_id"])
    assert second.status_code == 201
    assert (second.json()["rows_added"], second.json()["rows_skipped"]) == (0, 50)
    assert len(transactions(authed_client, account_id)) == 50


def test_chaque_operation_garde_la_trace_de_son_fichier(authed_client: TestClient) -> None:
    account_id = pea(authed_client)
    summary = import_all(authed_client, account_id, fixture("courtier_a_50_lignes.csv"), KINDS)
    imported = {item["import_id"] for item in transactions(authed_client, account_id)}
    assert imported == {summary["import_id"]}


def test_un_export_plus_recent_n_ajoute_que_les_nouvelles_lignes(authed_client: TestClient) -> None:
    account_id = pea(authed_client)
    base = fixture("courtier_a_50_lignes.csv").decode("windows-1252")
    import_all(authed_client, account_id, base.encode("windows-1252"), KINDS)
    extra = "30/12/2024;Versement;Versement espèces;;;;250,00;;\n"
    later = (base.rstrip("\r\n") + "\n" + extra).encode("windows-1252")
    summary = import_all(authed_client, account_id, later, KINDS)
    assert (summary["rows_added"], summary["rows_skipped"]) == (1, 50)


def test_deux_achats_identiques_du_meme_jour_ne_sont_pas_des_doublons(
    authed_client: TestClient,
) -> None:
    account_id = pea(authed_client)
    content = fixture("doublons_meme_jour.csv")
    first = import_all(authed_client, account_id, content, KINDS)
    assert (first["rows_added"], first["rows_skipped"]) == (3, 0)
    second = import_all(authed_client, account_id, content, KINDS)
    assert (second["rows_added"], second["rows_skipped"]) == (0, 3)
    assert len(transactions(authed_client, account_id)) == 3


def test_identifiant_externe_l_emporte_sur_l_empreinte(authed_client: TestClient) -> None:
    account_id = pea(authed_client)
    line = "03/01/2024;Versement;Versement espèces;;;;100,00;;"
    import_all(authed_client, account_id, csv_bytes(line + "REF-1"))
    # Même contenu, autre référence : c'est une autre opération.
    other = import_all(authed_client, account_id, csv_bytes(line + "REF-2"))
    assert other["rows_added"] == 1
    # Même référence, autre contenu : c'est la même opération.
    changed = "03/01/2024;Versement;Versement corrigé;;;;999,00;;REF-1"
    same = import_all(authed_client, account_id, csv_bytes(changed))
    assert (same["rows_added"], same["rows_skipped"]) == (0, 1)
    assert len(transactions(authed_client, account_id)) == 2


def test_une_meme_reference_deux_fois_dans_le_fichier(authed_client: TestClient) -> None:
    account_id = pea(authed_client)
    line = "03/01/2024;Versement;Versement espèces;;;;100,00;;REF-1"
    summary = import_all(authed_client, account_id, csv_bytes(line, line))
    assert (summary["rows_added"], summary["rows_skipped"]) == (1, 1)


def test_le_parametrage_enregistre_est_propose_au_fichier_suivant(
    authed_client: TestClient,
) -> None:
    account_id = pea(authed_client)
    content = fixture("courtier_a_50_lignes.csv")
    shown = preview(authed_client, account_id, content).json()
    done = commit(
        authed_client,
        shown["preview_id"],
        confirm_rejected=True,
        save_mapping_as="Courtier A",
        instrument_resolutions=[
            {"key": item["key"], "action": "create", "kind": KINDS[item["isin"]]}
            for item in shown["unknown_instruments"]
        ],
    )
    assert done.status_code == 201
    saved = authed_client.get(f"{API}/import-mappings").json()
    assert [item["name"] for item in saved] == ["Courtier A"]
    assert saved[0]["columns"] == COLUMNS
    assert saved[0]["encoding"] == "windows-1252" and saved[0]["delimiter"] == ";"

    # Un nouveau fichier du même établissement : aucune correspondance à fournir.
    proposed = preview(authed_client, account_id, content, columns=None).json()
    assert proposed["mapping_id"] == saved[0]["id"]
    assert proposed["columns"] == COLUMNS
    assert proposed["rows_duplicate"] == 50


def test_sans_correspondance_ni_parametrage_l_apercu_ne_lit_aucune_ligne(
    authed_client: TestClient,
) -> None:
    account_id = pea(authed_client)
    body = preview(
        authed_client, account_id, fixture("courtier_a_50_lignes.csv"), columns=None
    ).json()
    assert body["mapping_id"] is None and body["columns"] == {}
    assert body["rows_valid"] == 0
    assert body["detected"]["headers"][0] == "Date"
    assert body["detected"]["delimiter"] == ";"


def test_cinq_cents_lignes_en_moins_d_une_minute_sans_doublon_a_la_reimportation(
    authed_client: TestClient,
) -> None:
    account_id = pea(authed_client)
    create_instrument(authed_client, isin=ETF_ISIN, name="ETF Exemple Monde")
    lines = ["02/01/2024;Versement;Versement espèces;;;;100000,00;;"]
    for i in range(499):
        day = 1 + i // 20
        month = 1 + i // 400
        line = (
            f"{day:02d}/{month:02d}/2024;Achat;ETF Exemple Monde;{ETF_ISIN};"
            f"{1 + i % 5};{40 + i % 7},50;;1,00;"
        )
        lines.append(line)
        if i % 11 == 0:
            lines.append(line)  # deux achats identiques le même jour
    content = csv_bytes(*lines[:500])

    started = time.perf_counter()
    shown = preview(authed_client, account_id, content).json()
    done = commit(authed_client, shown["preview_id"], confirm_rejected=True)
    elapsed = time.perf_counter() - started
    assert done.status_code == 201, done.text
    assert done.json()["rows_added"] == 500
    assert elapsed < 60

    again = import_all(authed_client, account_id, content)
    assert (again["rows_added"], again["rows_skipped"]) == (0, 500)
    assert len(transactions(authed_client, account_id)) == 500
