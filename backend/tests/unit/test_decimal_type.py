"""Principe III : montants, quantités, prix et taux sont stockés en texte décimal exact."""

from decimal import Decimal

import pytest
import sqlalchemy as sa

from finance.db.types import DecimalText

metadata = sa.MetaData()
values = sa.Table(
    "values_under_test",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("v", DecimalText()),
)


@pytest.fixture
def plain_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    return engine


def bind(value: object) -> str | None:
    return DecimalText().process_bind_param(value, sa.engine.default.DefaultDialect())  # type: ignore[arg-type]


def test_roundtrip_keeps_exact_decimal(plain_engine: sa.Engine) -> None:
    with plain_engine.begin() as conn:
        conn.execute(values.insert().values(id=1, v=Decimal("90.199")))
        result = conn.execute(sa.select(values.c.v)).scalar_one()
    assert isinstance(result, Decimal)
    assert result == Decimal("90.199")


def test_value_is_stored_as_canonical_text(plain_engine: sa.Engine) -> None:
    with plain_engine.begin() as conn:
        conn.execute(values.insert().values(id=1, v=Decimal("90.199")))
        raw = conn.execute(sa.text("SELECT v, typeof(v) FROM values_under_test")).one()
    assert raw == ("90.199", "text")


def test_binary_sum_pitfall_is_avoided(plain_engine: sa.Engine) -> None:
    with plain_engine.begin() as conn:
        conn.execute(
            values.insert(), [{"id": 1, "v": Decimal("0.1")}, {"id": 2, "v": Decimal("0.2")}]
        )
        rows = conn.execute(sa.select(values.c.v)).scalars().all()
    assert sum(rows, Decimal(0)) == Decimal("0.3")


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        (Decimal("1.50"), "1.5"),
        (Decimal("100"), "100"),
        (Decimal("1E+3"), "1000"),
        (Decimal("0.000001"), "0.000001"),
        (Decimal("-2.675"), "-2.675"),
        (Decimal("-0"), "0"),
        (Decimal("0.00"), "0"),
        (5, "5"),
        ("12.50", "12.5"),
        ("-0.10", "-0.1"),
    ],
)
def test_canonical_form(given: object, stored: str) -> None:
    assert bind(given) == stored


def test_stored_text_never_uses_scientific_notation() -> None:
    for given in (Decimal("1E+30"), Decimal("1E-12"), Decimal("123456789.000000001")):
        text = bind(given)
        assert text is not None
        assert "e" not in text.lower()


def test_none_is_preserved() -> None:
    assert bind(None) is None
    assert DecimalText().process_result_value(None, sa.engine.default.DefaultDialect()) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [1.5, 0.0, True, False, b"1"])
def test_float_and_non_numeric_types_are_rejected(bad: object) -> None:
    with pytest.raises(TypeError):
        bind(bad)


@pytest.mark.parametrize("bad", ["1e3", "1E-2", "NaN", "Infinity", "-inf", "", "abc", "1,5", " "])
def test_invalid_text_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="décimal"):
        bind(bad)


@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_decimals_are_rejected(bad: Decimal) -> None:
    with pytest.raises(ValueError, match="décimal"):
        bind(bad)
