"""FR-028 : 12 à 128 caractères, hors liste des mots de passe courants."""

import time

import pytest

from finance.auth.passwords import (
    MAX_LENGTH,
    MIN_LENGTH,
    PasswordPolicyError,
    strip_edges,
    validate_password,
)


def test_bounds_are_the_ones_of_the_specification() -> None:
    assert (MIN_LENGTH, MAX_LENGTH) == (12, 128)


@pytest.mark.parametrize(
    "password",
    [
        "tulipe-bleue-47-horizon",
        "a1b2c3d4e5f6",
        "x" * 11 + "y",  # 12 caractères, pas une répétition d'un seul caractère
        "é" * 6 + "ü" * 6 + "z",
        "Mot de passe avec espaces 77",
        "🔒" * 6 + "abcdef",
        "p" * 100 + "q" * 28,  # 128 caractères exactement
    ],
)
def test_accepts_reasonable_passwords(password: str) -> None:
    validate_password(password)


@pytest.mark.parametrize("password", ["", "court", "onze-chars!", "x" * 129])
def test_rejects_wrong_length(password: str) -> None:
    with pytest.raises(PasswordPolicyError, match="caractères"):
        validate_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "password1234",
        "Password1234!",
        "motdepasse123",
        "MotDePasse2024",
        "passwordpassword",
        "azertyuiop123",
        "qwertyuiop12",
        "iloveyou12345",
        "changeme1234",
    ],
)
def test_rejects_common_passwords(password: str) -> None:
    with pytest.raises(PasswordPolicyError, match="courant"):
        validate_password(password)


@pytest.mark.parametrize(
    "password",
    [
        "aaaaaaaaaaaa",
        "123456789012",
        "abcdefghijkl",
        "987654321098",
        "abcabcabcabc",
        "121212121212",
    ],
)
def test_rejects_trivial_patterns(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_error_message_never_contains_the_password() -> None:
    secret = "motdepasse123"  # noqa: S105 - mot de passe volontairement faible
    with pytest.raises(PasswordPolicyError) as raised:
        validate_password(secret)
    assert secret not in str(raised.value)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("password1234", "password"),
        ("1234password", "password"),
        ("--pass word!!", "pass word"),
        ("p@ssw0rd99", "p@ssw0rd"),
        ("12345", ""),
        ("", ""),
        ("é-motdepasse-é", "é-motdepasse-é"),
    ],
)
def test_strip_edges_removes_non_letters_at_both_ends(given: str, expected: str) -> None:
    assert strip_edges(given) == expected


def test_strip_edges_is_linear_on_adversarial_input() -> None:
    """Réponse à l'alerte CodeQL py/polynomial-redos : aucune expression rationnelle."""
    started = time.perf_counter()
    for text in ("0" * 200_000 + "a", "a" + "0" * 200_000, "0!" * 100_000 + "a"):
        strip_edges(text)
    assert time.perf_counter() - started < 1.0
