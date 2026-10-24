"""data-model.md : ISIN « 12 caractères alphanumériques avec clé de contrôle valide »."""

import pytest

from finance.domain.isin import is_valid_isin, normalize_isin

VALID = [
    "US0378331005",
    "FR0000120271",
    "IE00B4L5Y983",
    "DE0007164600",
    "GB0002634946",
    "LU1681043599",
]


@pytest.mark.parametrize("isin", VALID)
def test_valid_isin(isin: str) -> None:
    assert is_valid_isin(isin)


@pytest.mark.parametrize(
    "isin",
    [
        "US0378331006",  # clé de contrôle fausse
        "US037833100",  # 11 caractères
        "US03783310055",  # 13 caractères
        "us0378331005",  # minuscules
        "US03783310*5",  # caractère non alphanumérique
        "1S0378331005",  # le code pays est fait de lettres
        "US037833100A",  # la clé de contrôle est un chiffre
        "",
        " US0378331005",
    ],
)
def test_invalid_isin(isin: str) -> None:
    assert not is_valid_isin(isin)


def test_normalize_strips_and_uppercases() -> None:
    assert normalize_isin("  fr0000120271 ") == "FR0000120271"


def test_normalize_refuses_invalid_value() -> None:
    with pytest.raises(ValueError, match="ISIN"):
        normalize_isin("FR0000120272")


def test_every_single_digit_change_is_detected() -> None:
    base = "FR0000120271"
    for index in range(2, 12):
        for digit in "0123456789":
            if digit == base[index]:
                continue
            candidate = base[:index] + digit + base[index + 1 :]
            assert not is_valid_isin(candidate), candidate
