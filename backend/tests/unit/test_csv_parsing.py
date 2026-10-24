"""FR-015, FR-017 : lecture d'un CSV générique, réglages détectés, lignes rejetées avec cause."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finance.domain.enums import TransactionType as T
from finance.importers.base import ImportFileError, ImportSettings
from finance.importers.csv_generic import detect_settings, parse_csv

FIXTURES = Path(__file__).parent.parent / "fixtures" / "csv"

COLUMNS = {
    "trade_date": "Date",
    "type": "Opération",
    "label": "Libellé",
    "isin": "ISIN",
    "instrument_name": "Libellé",
    "quantity": "Quantité",
    "unit_price": "Cours",
    "amount": "Montant",
    "fees": "Frais",
    "external_id": "Référence",
}
FR = ImportSettings(
    delimiter=";",
    encoding="windows-1252",
    date_format="%d/%m/%Y",
    decimal_separator=",",
    columns=COLUMNS,
)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class TestDetection:
    def test_fichier_de_courtier_francais(self):
        detected = detect_settings(fixture("courtier_a_50_lignes.csv"))
        assert detected.encoding == "windows-1252"
        assert detected.delimiter == ";"
        assert detected.date_format == "%d/%m/%Y"
        assert detected.decimal_separator == ","
        assert detected.headers[:3] == ["Date", "Opération", "Libellé"]
        assert len(detected.headers) == 9

    def test_utf8_avec_et_sans_marque_d_ordre_des_octets(self):
        text = "Date;Libellé\n02/01/2024;Dépôt\n"
        assert detect_settings(text.encode("utf-8")).encoding == "utf-8"
        assert detect_settings(b"\xef\xbb\xbf" + text.encode("utf-8")).encoding == "utf-8-sig"

    def test_virgule_comme_separateur_et_point_decimal(self):
        detected = detect_settings(b"Date,Type,Amount\n2024-01-02,Deposit,1000.50\n")
        assert detected.delimiter == ","
        assert detected.decimal_separator == "."
        assert detected.date_format == "%Y-%m-%d"

    def test_tabulation(self):
        detected = detect_settings(b"Date\tType\tAmount\n02/01/2024\tDeposit\t10,5\n")
        assert detected.delimiter == "\t"

    def test_date_ambigue_lue_jour_mois_annee(self):
        detected = detect_settings(b"Date;Montant\n03/04/2024;10,00\n")
        assert detected.date_format == "%d/%m/%Y"

    def test_date_a_deux_chiffres_pour_l_annee(self):
        detected = detect_settings(b"Date;Montant\n13/04/24;10,00\n")
        assert detected.date_format == "%d/%m/%y"

    def test_separateur_decimal_par_defaut_virgule(self):
        detected = detect_settings(b"Date;Montant\n13/04/2024;10\n")
        assert detected.decimal_separator == ","

    @pytest.mark.parametrize("content", [b"", b"   \n\n"])
    def test_fichier_vide(self, content: bytes):
        with pytest.raises(ImportFileError, match="vide"):
            detect_settings(content)

    def test_fichier_vide_du_jeu_d_essai(self):
        with pytest.raises(ImportFileError, match="vide"):
            detect_settings(fixture("vide.csv"))


class TestParsing:
    def test_cinquante_lignes_valides(self):
        result = parse_csv(fixture("courtier_a_50_lignes.csv"), FR)
        assert len(result.rows) == 50
        assert result.rejected == []
        assert [row.line for row in result.rows] == list(range(2, 52))

    def test_valeurs_lues_avec_les_bons_formats(self):
        rows = parse_csv(fixture("courtier_a_50_lignes.csv"), FR).rows
        first, buy = rows[0], rows[1]
        assert first.type is T.DEPOSIT
        assert first.trade_date == date(2024, 1, 5)
        assert first.amount == Decimal("12500.00")  # « 12 500,00 » avec espace insécable
        assert buy.type is T.BUY
        assert buy.instrument_name == "ETF Exemple Monde"
        assert buy.isin == "FR0000000010"
        assert buy.quantity == Decimal("1.5")
        assert buy.unit_price == Decimal("41.35")
        assert buy.amount == Decimal("62.02")
        assert buy.fees == Decimal("1.50")

    def test_frais_absents_valent_zero(self):
        assert parse_csv(fixture("courtier_a_50_lignes.csv"), FR).rows[0].fees == Decimal(0)

    def test_aucun_flottant(self):
        for row in parse_csv(fixture("courtier_a_50_lignes.csv"), FR).rows:
            for value in (row.quantity, row.unit_price, row.amount, row.fees):
                assert value is None or isinstance(value, Decimal)

    def test_lignes_invalides_listees_avec_leur_cause(self):
        result = parse_csv(fixture("lignes_invalides.csv"), FR)
        assert [row.line for row in result.rows] == [2, 7]
        reasons = {item.line: item.reason for item in result.rejected}
        assert sorted(reasons) == [3, 4, 5, 6]
        assert "date" in reasons[3].lower() and "31/02/2024" in reasons[3]
        assert "montant" in reasons[4].lower()
        assert "type" in reasons[5].lower() and "Spéculation" in reasons[5]
        assert "abc" in reasons[6]

    def test_une_ligne_rejetee_ne_bloque_pas_les_suivantes(self):
        result = parse_csv(fixture("lignes_invalides.csv"), FR)
        assert result.rows[-1].isin == "FR0000000010"

    def test_point_decimal_et_virgule_des_milliers(self):
        settings = ImportSettings(
            ",",
            "utf-8",
            "%Y-%m-%d",
            ".",
            {"trade_date": "Date", "type": "Type", "amount": "Amount"},
        )
        content = b'Date,Type,Amount\n2024-01-02,Deposit,"1,250.50"\n'
        assert parse_csv(content, settings).rows[0].amount == Decimal("1250.50")

    def test_champ_entre_guillemets_contenant_le_separateur(self):
        content = 'Date;Opération;Libellé;Montant\n02/01/2024;Versement;"Virement; salaire";10,00\n'
        settings = ImportSettings(
            ";",
            "utf-8",
            "%d/%m/%Y",
            ",",
            {
                "trade_date": "Date",
                "type": "Opération",
                "label": "Libellé",
                "amount": "Montant",
            },
        )
        assert parse_csv(content.encode(), settings).rows[0].label == "Virement; salaire"

    def test_montant_negatif_lu_en_valeur_absolue(self):
        content = b"Date;Op;Montant\n02/01/2024;Frais;-2,50\n"
        settings = ImportSettings(
            ";", "utf-8", "%d/%m/%Y", ",", {"trade_date": "Date", "type": "Op", "amount": "Montant"}
        )
        row = parse_csv(content, settings).rows[0]
        assert row.type is T.FEE and row.amount == Decimal("2.50")

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "1e400", "12,3,4"])
    def test_nombres_non_finis_ou_illisibles_rejetes(self, value: str):
        content = f"Date;Op;Montant\n02/01/2024;Versement;{value}\n".encode()
        settings = ImportSettings(
            ";", "utf-8", "%d/%m/%Y", ",", {"trade_date": "Date", "type": "Op", "amount": "Montant"}
        )
        result = parse_csv(content, settings)
        assert result.rows == [] and len(result.rejected) == 1

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("Achat", T.BUY),
            ("ACHAT", T.BUY),
            ("BUY", T.BUY),
            ("Vente", T.SELL),
            ("Dividende", T.DIVIDEND),
            ("Dividendes", T.DIVIDEND),
            ("Distribution", T.DISTRIBUTION),
            ("Intérêts", T.INTEREST),
            ("Interets", T.INTEREST),
            ("Frais", T.FEE),
            ("Retrait", T.WITHDRAWAL),
            ("Versement", T.DEPOSIT),
            ("Dépôt", T.DEPOSIT),
            ("Abondement", T.EMPLOYER_MATCH),
        ],
    )
    def test_vocabulaire_des_types(self, word: str, expected: T):
        row = f"02/01/2024;{word};10,00;1;10,00;FR0000000010"
        content = f"Date;Op;Montant;Quantité;Cours;ISIN\n{row}\n".encode()
        settings = ImportSettings(
            ";",
            "utf-8",
            "%d/%m/%Y",
            ",",
            {
                "trade_date": "Date",
                "type": "Op",
                "amount": "Montant",
                "quantity": "Quantité",
                "unit_price": "Cours",
                "isin": "ISIN",
            },
        )
        assert parse_csv(content, settings).rows[0].type is expected

    def test_identifiant_externe_lu(self):
        content = (
            b"Date;Op;Montant;Ref\n02/01/2024;Versement;10,00;ABC-1\n02/01/2024;Versement;10,00;\n"
        )
        settings = ImportSettings(
            ";",
            "utf-8",
            "%d/%m/%Y",
            ",",
            {"trade_date": "Date", "type": "Op", "amount": "Montant", "external_id": "Ref"},
        )
        rows = parse_csv(content, settings).rows
        assert [row.external_id for row in rows] == ["ABC-1", None]

    def test_colonne_declaree_mais_absente_du_fichier(self):
        settings = ImportSettings(
            ";", "utf-8", "%d/%m/%Y", ",", {"trade_date": "Date", "type": "Type inexistant"}
        )
        with pytest.raises(ImportFileError, match="Type inexistant"):
            parse_csv(b"Date;Op\n02/01/2024;Versement\n", settings)

    def test_correspondance_sans_date_ni_type(self):
        settings = ImportSettings(";", "utf-8", "%d/%m/%Y", ",", {"amount": "Montant"})
        with pytest.raises(ImportFileError, match="date"):
            parse_csv(b"Montant\n10\n", settings)

    def test_fichier_avec_seulement_l_en_tete(self):
        result = parse_csv(
            b"Date;Op\n",
            ImportSettings(";", "utf-8", "%d/%m/%Y", ",", {"trade_date": "Date", "type": "Op"}),
        )
        assert result.rows == [] and result.rejected == []

    def test_fichier_vide(self):
        with pytest.raises(ImportFileError, match="vide"):
            parse_csv(fixture("vide.csv"), FR)

    def test_encodage_incompatible(self):
        settings = ImportSettings(";", "utf-8", "%d/%m/%Y", ",", COLUMNS)
        with pytest.raises(ImportFileError, match="encodage"):
            parse_csv(fixture("courtier_a_50_lignes.csv"), settings)

    def test_encodage_inconnu(self):
        settings = ImportSettings(";", "pas-un-encodage", "%d/%m/%Y", ",", COLUMNS)
        with pytest.raises(ImportFileError, match="encodage"):
            parse_csv(fixture("courtier_a_50_lignes.csv"), settings)
