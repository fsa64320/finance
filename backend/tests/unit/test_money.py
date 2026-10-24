"""Principe III : un montant garde sa devise, l'arrondi n'a lieu qu'à l'affichage."""

from decimal import Decimal

import pytest

from finance.domain.money import CurrencyMismatchError, Money


def eur(value: str) -> Money:
    return Money(Decimal(value), "EUR")


def test_amount_must_be_decimal_not_float() -> None:
    with pytest.raises(TypeError):
        Money(1.5, "EUR")  # type: ignore[arg-type]


def test_integers_are_accepted_as_exact_values() -> None:
    assert Money(3, "EUR").amount == Decimal(3)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["eur", "EU", "EURO", "E1R", "", "€"])
def test_currency_must_be_three_uppercase_letters(bad: str) -> None:
    with pytest.raises(ValueError, match="devise"):
        Money(Decimal(1), bad)


def test_addition_is_exact() -> None:
    assert eur("0.1") + eur("0.2") == eur("0.3")


def test_subtraction_and_negation() -> None:
    assert eur("10") - eur("2.5") == eur("7.5")
    assert -eur("2.5") == eur("-2.5")


def test_mixed_currencies_are_refused() -> None:
    with pytest.raises(CurrencyMismatchError):
        eur("1") + Money(Decimal(1), "USD")
    with pytest.raises(CurrencyMismatchError):
        eur("1") - Money(Decimal(1), "USD")


def test_multiplication_by_decimal_and_int() -> None:
    assert eur("90.199") * Decimal(10) == eur("901.99")
    assert eur("2") * 3 == eur("6")


def test_multiplication_by_float_is_refused() -> None:
    with pytest.raises(TypeError):
        eur("2") * 1.5  # type: ignore[operator]


def test_money_is_immutable() -> None:
    amount = eur("1")
    with pytest.raises(AttributeError):
        amount.amount = Decimal(2)  # type: ignore[misc]


def test_equality_requires_same_currency() -> None:
    assert eur("1") != Money(Decimal(1), "USD")


def test_rounding_happens_only_at_display() -> None:
    value = eur("2.675")
    assert value.amount == Decimal("2.675")
    assert value.to_display() == Decimal("2.68")


def test_display_rounding_is_half_up_away_from_zero() -> None:
    assert eur("-2.675").to_display() == Decimal("-2.68")
    assert eur("0.004").to_display() == Decimal("0.00")
    assert eur("0.005").to_display() == Decimal("0.01")


def test_display_rounding_with_other_places() -> None:
    assert eur("90.199").to_display(places=3) == Decimal("90.199")
    assert eur("90.1994").to_display(places=3) == Decimal("90.199")
