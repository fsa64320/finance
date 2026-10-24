from pathlib import Path

import pytest

from finance.config import PRICE_FETCH_DEFAULT, Settings, load_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("FINANCE_DATA_DIR", "FINANCE_HOST", "FINANCE_PORT"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings == Settings(data_dir=Path("/data"), host="127.0.0.1", port=8000)


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_DATA_DIR", "/srv/finance-data")
    monkeypatch.setenv("FINANCE_HOST", "0.0.0.0")  # noqa: S104 - valeur de test
    monkeypatch.setenv("FINANCE_PORT", "9000")
    settings = load_settings()
    assert settings.data_dir == Path("/srv/finance-data")
    assert settings.host == "0.0.0.0"  # noqa: S104
    assert settings.port == 9000


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_PORT", "pas-un-port")
    with pytest.raises(ValueError, match="FINANCE_PORT"):
        load_settings()


def test_port_out_of_range_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_PORT", "70000")
    with pytest.raises(ValueError, match="FINANCE_PORT"):
        load_settings()


def test_price_fetch_is_off_by_default() -> None:
    """Constitution v1.1.0, principe I : rien ne sort avant un choix explicite."""
    assert PRICE_FETCH_DEFAULT is False


def test_allowed_origins_and_static_dir_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FINANCE_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("FINANCE_STATIC_DIR", raising=False)
    settings = load_settings()
    assert settings.allowed_origins == ()
    assert settings.static_dir is None


def test_allowed_origins_and_static_dir_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_ALLOWED_ORIGINS", " https://a.example , https://b.example ,, ")
    monkeypatch.setenv("FINANCE_STATIC_DIR", "/srv/static")
    settings = load_settings()
    assert settings.allowed_origins == ("https://a.example", "https://b.example")
    assert settings.static_dir == Path("/srv/static")
