"""data-model.md, effets de trésorerie : qui ajoute, qui retire, et de combien."""

from decimal import Decimal

import pytest

from finance.domain.enums import TransactionType as T
from finance.domain.ledger import cash_effect

ADDING = [T.DEPOSIT, T.DIVIDEND, T.DISTRIBUTION, T.INTEREST, T.EMPLOYER_MATCH, T.TRANSFER_IN]
REMOVING = [T.WITHDRAWAL, T.FEE, T.TRANSFER_OUT]


@pytest.mark.parametrize("kind", ADDING)
def test_inflows_add_the_amount(kind: T) -> None:
    assert cash_effect(kind, amount=Decimal("125.40")) == Decimal("125.40")


@pytest.mark.parametrize("kind", REMOVING)
def test_outflows_remove_the_amount(kind: T) -> None:
    assert cash_effect(kind, amount=Decimal("125.40")) == Decimal("-125.40")


def test_buy_removes_quantity_times_price_plus_fees() -> None:
    effect = cash_effect(
        T.BUY, quantity=Decimal("10"), unit_price=Decimal("90"), fees=Decimal("1.99")
    )
    assert effect == Decimal("-901.99")


def test_sell_adds_quantity_times_price_minus_fees() -> None:
    effect = cash_effect(
        T.SELL, quantity=Decimal("5"), unit_price=Decimal("92.5"), fees=Decimal("1.99")
    )
    assert effect == Decimal("460.51")


def test_fees_default_to_zero() -> None:
    assert cash_effect(T.BUY, quantity=Decimal(2), unit_price=Decimal("10.5")) == Decimal("-21.0")


def test_arithmetic_is_exact_where_floats_drift() -> None:
    effect = cash_effect(
        T.BUY, quantity=Decimal("3"), unit_price=Decimal("0.1"), fees=Decimal("0.05")
    )
    assert effect == Decimal("-0.35")
    assert cash_effect(T.BUY, quantity=Decimal("0.000001"), unit_price=Decimal("3")) == Decimal(
        "-0.000003"
    )


@pytest.mark.parametrize("kind", [*ADDING, *REMOVING])
def test_cash_flows_need_an_amount(kind: T) -> None:
    with pytest.raises(ValueError, match="montant"):
        cash_effect(kind)


@pytest.mark.parametrize("kind", [*ADDING, *REMOVING])
@pytest.mark.parametrize("amount", [Decimal(0), Decimal("-5")])
def test_amount_must_be_strictly_positive(kind: T, amount: Decimal) -> None:
    with pytest.raises(ValueError, match="positif"):
        cash_effect(kind, amount=amount)


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
def test_trades_need_quantity_and_price(kind: T) -> None:
    with pytest.raises(ValueError, match="quantité"):
        cash_effect(kind, unit_price=Decimal(1))
    with pytest.raises(ValueError, match="prix"):
        cash_effect(kind, quantity=Decimal(1))


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
def test_trades_refuse_a_free_amount(kind: T) -> None:
    with pytest.raises(ValueError, match="montant"):
        cash_effect(kind, amount=Decimal(10), quantity=Decimal(1), unit_price=Decimal(1))


def test_fees_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="frais"):
        cash_effect(T.BUY, quantity=Decimal(1), unit_price=Decimal(1), fees=Decimal("-1"))


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
@pytest.mark.parametrize(
    ("quantity", "price"), [(Decimal(0), Decimal(1)), (Decimal(1), Decimal(0))]
)
def test_quantity_and_price_must_be_strictly_positive(
    kind: T, quantity: Decimal, price: Decimal
) -> None:
    with pytest.raises(ValueError, match="positi"):
        cash_effect(kind, quantity=quantity, unit_price=price)
