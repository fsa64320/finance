"""FR-023 : répartition par classe d'actifs, poids dont la somme vaut exactement 100."""

from datetime import date
from decimal import Decimal

import pytest
from finance.domain.allocation import AssetClass, asset_class_of, compute_allocation, split_weights
from hypothesis import given, settings
from hypothesis import strategies as st

from finance.domain.enums import InstrumentKind as K
from finance.domain.valuation import AccountValue, PositionValue
from tests.domain_helpers import d


def position(kind: K, value: str | None, identifier: str = "x") -> PositionValue:
    return PositionValue(
        instrument_id=identifier,
        kind=kind,
        quantity=d("1"),
        total_cost=d("0"),
        unit_cost=None,
        price=None,
        price_date=None,
        value=None if value is None else d(value),
        estimated=False,
    )


def account_value(cash: str, *positions: PositionValue, identifier: str = "a") -> AccountValue:
    return AccountValue(
        account_id=identifier,
        as_of=date(2026, 12, 31),
        currency="EUR",
        cash=d(cash),
        positions=positions,
        total=d(cash) + sum((p.value or Decimal(0) for p in positions), Decimal(0)),
        estimated=False,
        warnings=(),
    )


def by_class(slices):  # type: ignore[no-untyped-def]
    return {s.asset_class: s for s in slices}


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (K.EQUITY, AssetClass.EQUITIES_ETF),
        (K.ETF, AssetClass.EQUITIES_ETF),
        (K.FUND, AssetClass.FUNDS),
        (K.FCPE, AssetClass.FUNDS),
        (K.SCPI, AssetClass.SCPI),
        (K.EURO_FUND, AssetClass.EURO_FUNDS),
        (K.CASH, AssetClass.CASH),
    ],
)
def test_instrument_kinds_map_to_asset_classes(kind: K, expected: AssetClass) -> None:
    assert asset_class_of(kind) is expected


def test_asset_class_values_follow_the_contract() -> None:
    assert [c.value for c in AssetClass] == ["equities_etf", "funds", "scpi", "euro_funds", "cash"]


def test_cash_and_positions_are_grouped_across_accounts() -> None:
    values = [
        account_value("100", position(K.ETF, "800"), position(K.FUND, "100"), identifier="a"),
        account_value("900", position(K.ETF, "200"), position(K.EURO_FUND, "500"), identifier="b"),
    ]
    slices = by_class(compute_allocation(values))
    assert slices[AssetClass.EQUITIES_ETF].value == d("1000")
    assert slices[AssetClass.FUNDS].value == d("100")
    assert slices[AssetClass.EURO_FUNDS].value == d("500")
    assert slices[AssetClass.CASH].value == d("1000")
    assert AssetClass.SCPI not in slices


def test_weights_are_percentages_that_add_up_to_exactly_100() -> None:
    values = [account_value("0", position(K.ETF, "800"), position(K.FUND, "200"))]
    slices = compute_allocation(values)
    assert [(s.asset_class, s.weight_percent) for s in slices] == [
        (AssetClass.EQUITIES_ETF, d("80")),
        (AssetClass.FUNDS, d("20")),
    ]


def test_thirds_are_rounded_so_that_the_sum_stays_100() -> None:
    values = [
        account_value(
            "100", position(K.ETF, "100"), position(K.FUND, "100"), position(K.EURO_FUND, "0")
        )
    ]
    slices = compute_allocation(values)
    weights = [s.weight_percent for s in slices]
    assert sum(weights) == d("100")
    assert sorted(weights) == [d("33.33"), d("33.33"), d("33.34")]


def test_single_class_weighs_100() -> None:
    assert [s.weight_percent for s in compute_allocation([account_value("500")])] == [d("100")]


def test_slices_follow_the_class_order() -> None:
    values = [
        account_value("1", position(K.EURO_FUND, "1"), position(K.SCPI, "1"), position(K.ETF, "1"))
    ]
    assert [s.asset_class for s in compute_allocation(values)] == [
        AssetClass.EQUITIES_ETF,
        AssetClass.SCPI,
        AssetClass.EURO_FUNDS,
        AssetClass.CASH,
    ]


def test_nothing_to_allocate_gives_no_slice() -> None:
    assert compute_allocation([]) == []
    assert compute_allocation([account_value("0")]) == []


def test_unvalued_positions_and_negative_classes_are_left_out() -> None:
    values = [account_value("-50", position(K.ETF, "100"), position(K.FUND, None))]
    slices = compute_allocation(values)
    assert [(s.asset_class, s.value, s.weight_percent) for s in slices] == [
        (AssetClass.EQUITIES_ETF, d("100"), d("100"))
    ]


def test_values_stay_exact() -> None:
    values = [account_value("0.1", position(K.ETF, "0.2"))]
    slices = by_class(compute_allocation(values))
    assert slices[AssetClass.EQUITIES_ETF].value == d("0.2")
    assert slices[AssetClass.CASH].value == d("0.1")


# ------------------------------------------------------------ split_weights


def test_split_weights_distributes_remainders_to_the_largest_fractions() -> None:
    assert split_weights([d("1"), d("1"), d("1")]) == [d("33.34"), d("33.33"), d("33.33")]


def test_split_weights_is_stable_for_ties() -> None:
    assert split_weights([d("1"), d("1")]) == [d("50"), d("50")]


def test_split_weights_rejects_empty_or_non_positive_totals() -> None:
    with pytest.raises(ValueError, match="positif"):
        split_weights([d("0")])
    with pytest.raises(ValueError, match="positif"):
        split_weights([])


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"), places=2),
        min_size=1,
        max_size=5,
    )
)
def test_weights_always_sum_to_exactly_100(amounts: list[Decimal]) -> None:
    weights = split_weights(amounts)
    assert sum(weights) == Decimal(100)
    assert all(weight >= 0 for weight in weights)
    for amount, weight in zip(amounts, weights, strict=True):
        exact = amount * 100 / sum(amounts)
        assert abs(weight - exact) <= Decimal("0.01")
