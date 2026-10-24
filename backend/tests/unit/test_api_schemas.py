"""Montants échangés en chaînes décimales, jamais en nombres JSON (principe III)."""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from finance.api.schemas import DecimalStr


class Line(BaseModel):
    amount: DecimalStr


def test_accepts_a_decimal_string() -> None:
    assert Line.model_validate({"amount": "90.199"}).amount == Decimal("90.199")


def test_json_output_is_a_canonical_string() -> None:
    assert Line(amount=Decimal("1.50")).model_dump_json() == '{"amount":"1.5"}'
    assert Line(amount=Decimal("1E+3")).model_dump(mode="json") == {"amount": "1000"}


@pytest.mark.parametrize("bad", [1.5, 90, True, None, "1e3", "NaN", "", "1,5"])
def test_rejects_json_numbers_and_malformed_text(bad: object) -> None:
    with pytest.raises(ValidationError):
        Line.model_validate({"amount": bad})


def test_json_number_in_raw_payload_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Line.model_validate_json('{"amount": 90.199}')
