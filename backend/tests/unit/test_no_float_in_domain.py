"""Principe III : aucun flottant dans le domaine (montants, quantités, prix, taux en Decimal)."""

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "finance" / "domain"


def find_float_usage(source: str) -> list[tuple[int, str]]:
    """Retourne (ligne, raison) pour chaque littéral, nom ou annotation flottant."""
    findings: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            findings.append((node.lineno, f"littéral flottant {node.value!r}"))
        elif isinstance(node, ast.Name) and node.id == "float":
            findings.append((node.lineno, "usage de float (appel ou annotation)"))
    return findings


def test_scanner_detects_float_literal() -> None:
    assert find_float_usage("x = 1.5\n") == [(1, "littéral flottant 1.5")]


def test_scanner_detects_float_call() -> None:
    assert [r for _, r in find_float_usage("y = float('1.5')\n")] == [
        "usage de float (appel ou annotation)"
    ]


def test_scanner_detects_float_annotation() -> None:
    assert find_float_usage("def f(a: float) -> int:\n    return 1\n")


def test_scanner_accepts_decimal_and_ints() -> None:
    source = "from decimal import Decimal\nx = Decimal('1.5')\nn = 3\n"
    assert find_float_usage(source) == []


def test_domain_package_has_no_float() -> None:
    offences = {
        str(path.relative_to(DOMAIN_DIR)): found
        for path in sorted(DOMAIN_DIR.rglob("*.py"))
        if (found := find_float_usage(path.read_text(encoding="utf-8")))
    }
    assert offences == {}, f"float interdit dans finance.domain : {offences}"
