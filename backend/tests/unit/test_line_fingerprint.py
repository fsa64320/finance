"""FR-018 : l'empreinte d'une ligne importée sert au dédoublonnage ; l'identifiant externe l'emporte."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from finance.domain.enums import TransactionType as T
from finance.domain.fingerprint import (
    LineFacts,
    fingerprint_lines,
    is_duplicate,
)

BASE = LineFacts(
    trade_date=date(2024, 1, 3),
    type=T.BUY,
    instrument_key="FR0000000011",
    quantity=Decimal("2"),
    unit_price=Decimal("40.00"),
    amount=Decimal("80.00"),
    fees=Decimal("1.50"),
    label="ETF Exemple Monde",
)


def one(facts: LineFacts, account: str = "a1") -> str:
    return fingerprint_lines(account, [facts])[0]


def test_stable_d_un_appel_a_l_autre():
    assert one(BASE) == one(BASE)
    assert len(one(BASE)) == 64


def test_zeros_de_fin_sans_effet():
    other = replace(BASE, quantity=Decimal("2.000"), unit_price=Decimal("40"), amount=Decimal("80.0"))
    assert one(other) == one(BASE)


def test_chaque_champ_change_l_empreinte():
    changes = {
        "trade_date": date(2024, 1, 4),
        "type": T.SELL,
        "instrument_key": "FR0000000029",
        "quantity": Decimal("3"),
        "unit_price": Decimal("41"),
        "amount": Decimal("81"),
        "fees": Decimal("2"),
        "label": "Autre libellé",
    }
    seen = {one(BASE)}
    for name, value in changes.items():
        fingerprint = one(replace(BASE, **{name: value}))
        assert fingerprint not in seen, name
        seen.add(fingerprint)


def test_le_compte_change_l_empreinte():
    assert one(BASE, "a1") != one(BASE, "a2")


def test_champs_absents_distincts_de_zero():
    assert one(replace(BASE, quantity=None)) != one(replace(BASE, quantity=Decimal(0)))


def test_deux_achats_identiques_du_meme_fichier_restent_distincts():
    first, second = fingerprint_lines("a1", [BASE, BASE])
    assert first != second


def test_le_rang_ne_depend_que_des_lignes_identiques():
    other = replace(BASE, quantity=Decimal("9"))
    alone = fingerprint_lines("a1", [BASE])
    mixed = fingerprint_lines("a1", [other, BASE, other, BASE])
    assert mixed[1] == alone[0]
    assert mixed[0] != mixed[2] and mixed[1] != mixed[3]


def test_un_export_plus_recent_retrouve_les_memes_empreintes():
    earlier = fingerprint_lines("a1", [BASE, BASE])
    later = fingerprint_lines("a1", [BASE, BASE, BASE])
    assert later[:2] == earlier
    assert later[2] not in earlier


class TestDoublon:
    def test_empreinte_connue(self):
        assert is_duplicate(None, "f1", known_external_ids=set(), known_fingerprints={"f1"})

    def test_empreinte_inconnue(self):
        assert not is_duplicate(None, "f2", known_external_ids=set(), known_fingerprints={"f1"})

    def test_identifiant_externe_connu_l_emporte_sur_une_empreinte_differente(self):
        assert is_duplicate("R-1", "nouvelle", known_external_ids={"R-1"}, known_fingerprints=set())

    def test_identifiant_externe_nouveau_l_emporte_sur_une_empreinte_connue(self):
        assert not is_duplicate("R-2", "f1", known_external_ids={"R-1"}, known_fingerprints={"f1"})
