"""Politique de mot de passe (FR-028) : 12 à 128 caractères, hors mots de passe courants.

La liste embarquée est volontairement courte : elle attrape les mots de passe les plus évidents
(mots courants avec chiffres, suites, répétitions, lignes de clavier). Elle ne remplace pas le choix
d'une vraie phrase de passe, qu'il vaut mieux encourager dans l'interface.
"""

import re

MIN_LENGTH = 12
MAX_LENGTH = 128

_EDGES = re.compile(r"^[\W\d_]+|[\W\d_]+$")
_LEET = str.maketrans({"@": "a", "0": "o", "$": "s", "3": "e", "1": "i", "!": "i", "5": "s"})

# Mots de base courants (français et anglais) ; les chiffres et symboles autour sont retirés avant
# comparaison, et un mot répété ("passwordpassword") est refusé aussi.
BASE_WORDS = frozenset(
    {
        "password", "passwort", "motdepasse", "monmotdepasse", "azerty", "azertyuiop", "qwerty",
        "qwertyuiop", "iloveyou", "jetaime", "changeme", "letmein", "welcome", "bienvenue",
        "administrator", "admin", "administrateur", "finance", "patrimoine", "monkey", "dragon",
        "football", "master", "login", "secret", "soleil", "chocolat", "marseille", "superman",
        "azertyuiopqsdfghjklm", "bonjour", "bonjour2024", "banque", "argent", "epargne",
    }
)  # fmt: skip

# Mots de passe longs très répandus (déjà normalisés en minuscules).
COMMON_PASSWORDS = frozenset(
    {
        "1q2w3e4r5t6y", "1qaz2wsx3edc", "qwertyuiopas", "azertyuiopqs", "password12345",
        "motdepasse1234", "letmein123456", "welcome12345", "iloveyou1234", "administrator1",
        "123456789abc", "abc123456789", "000000000000", "111111111111", "123123123123",
        "azerty123456", "qwerty123456", "passw0rd1234", "p@ssw0rd1234", "changeme1234",
    }
)  # fmt: skip

_SEQUENCES = (
    "01234567890123456789",
    "98765432109876543210",
    "abcdefghijklmnopqrstuvwxyz",
    "zyxwvutsrqponmlkjihgfedcba",
)
_KEYBOARD_ROWS = ("azertyuiop", "qwertyuiop", "qsdfghjklm", "asdfghjkl", "poiuytreza", "poiuytrewq")


class PasswordPolicyError(ValueError):
    """Mot de passe refusé ; le message explique la règle sans jamais citer le mot de passe."""


def _is_repetition(text: str) -> bool:
    for size in range(1, 5):
        pattern = text[:size]
        if (pattern * (len(text) // size + 1))[: len(text)] == text:
            return True
    return False


def _is_repeated_base_word(core: str) -> bool:
    return any(
        core == word * count for word in BASE_WORDS for count in range(1, 6) if len(word) >= 5
    )


def _is_common(lowered: str) -> bool:
    if lowered in COMMON_PASSWORDS:
        return True
    if any(row in lowered for row in _KEYBOARD_ROWS):
        return True
    core = _EDGES.sub("", lowered).translate(_LEET)
    return core in BASE_WORDS or _is_repeated_base_word(core)


def validate_password(password: str) -> None:
    """Lève `PasswordPolicyError` si le mot de passe ne respecte pas la politique."""
    if not MIN_LENGTH <= len(password) <= MAX_LENGTH:
        raise PasswordPolicyError(
            f"Le mot de passe doit faire entre {MIN_LENGTH} et {MAX_LENGTH} caractères."
        )
    lowered = password.casefold()
    if _is_common(lowered):
        raise PasswordPolicyError(
            "Ce mot de passe est trop courant : choisissez une phrase de passe plus personnelle."
        )
    if _is_repetition(lowered) or any(lowered in sequence for sequence in _SEQUENCES):
        raise PasswordPolicyError(
            "Ce mot de passe est trop simple (répétition ou suite de caractères)."
        )
