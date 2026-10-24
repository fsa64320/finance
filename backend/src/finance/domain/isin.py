"""Code ISIN : deux lettres de pays, neuf alphanumériques et un chiffre de contrôle (12 en tout)."""

import re

_SHAPE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def _check_digit_is_valid(isin: str) -> bool:
    # Chaque lettre devient deux chiffres (A=10 … Z=35), puis algorithme de Luhn.
    digits = "".join(str(int(char, 36)) for char in isin)
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def is_valid_isin(value: str) -> bool:
    """Vrai si `value` est un ISIN exact : majuscules, sans espace, clé de contrôle correcte."""
    return bool(_SHAPE.fullmatch(value)) and _check_digit_is_valid(value)


def normalize_isin(value: str) -> str:
    """Retire les espaces autour, passe en majuscules et refuse un ISIN invalide."""
    candidate = value.strip().upper()
    if not is_valid_isin(candidate):
        raise ValueError(f"ISIN invalide : {value!r}")
    return candidate
