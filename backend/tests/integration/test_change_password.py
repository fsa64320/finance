"""FR-033 : changer le mot de passe rechiffre les données ; l'ancien cesse de fonctionner."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance.config import Settings
from finance.db.engine import WrongPasswordError, open_database
from finance.main import create_app
from tests.api_helpers import API, create_account
from tests.conftest import API_PASSWORD, FakeClock

NEW_PASSWORD = "cerisier-rouge-83-lagune"  # noqa: S105 - valeur jetable des tests


def change(client: TestClient, current: str = API_PASSWORD, new: str = NEW_PASSWORD):  # type: ignore[no-untyped-def]
    return client.post(
        f"{API}/auth/change-password", json={"current_password": current, "new_password": new}
    )


def test_the_data_stay_readable_with_the_new_password(authed_client: TestClient) -> None:
    create_account(authed_client)
    assert change(authed_client).status_code == 204
    names = [a["name"] for a in authed_client.get(f"{API}/accounts").json()]
    assert names == ["PEA Courtier A"]  # la session en cours reste valide


def test_the_old_password_is_refused_afterwards_and_the_new_one_works(
    authed_client: TestClient,
) -> None:
    create_account(authed_client)
    assert change(authed_client).status_code == 204
    authed_client.post(f"{API}/auth/lock")
    old = authed_client.post(f"{API}/auth/unlock", json={"password": API_PASSWORD})
    assert old.status_code == 401
    new = authed_client.post(f"{API}/auth/unlock", json={"password": NEW_PASSWORD})
    assert new.status_code == 204
    assert [a["name"] for a in authed_client.get(f"{API}/accounts").json()] == ["PEA Courtier A"]


def test_the_database_file_no_longer_opens_with_the_old_password(
    authed_client: TestClient, tmp_path: Path
) -> None:
    assert change(authed_client).status_code == 204
    database = tmp_path / "data" / "finance.db"
    with pytest.raises(WrongPasswordError):
        open_database(database, API_PASSWORD)
    open_database(database, NEW_PASSWORD).dispose()


def test_it_survives_a_restart(authed_client: TestClient, tmp_path: Path) -> None:
    create_account(authed_client)
    assert change(authed_client).status_code == 204
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    with TestClient(create_app(settings), base_url="http://testserver") as restarted:
        assert (
            restarted.post(f"{API}/auth/unlock", json={"password": API_PASSWORD}).status_code == 401
        )
        assert (
            restarted.post(f"{API}/auth/unlock", json={"password": NEW_PASSWORD}).status_code == 204
        )
        assert len(restarted.get(f"{API}/accounts").json()) == 1


def test_a_wrong_current_password_changes_nothing(authed_client: TestClient) -> None:
    response = change(authed_client, current="pas-le-bon-mot-de-passe")
    assert response.status_code == 401
    authed_client.post(f"{API}/auth/lock")
    assert (
        authed_client.post(f"{API}/auth/unlock", json={"password": API_PASSWORD}).status_code == 204
    )


def test_wrong_current_passwords_are_throttled_like_unlock_attempts(
    authed_client: TestClient,
) -> None:
    codes = [
        change(authed_client, current=f"mauvais-mot-de-passe-{i}").status_code for i in range(7)
    ]
    assert codes[:5] == [401] * 5
    assert 429 in codes[5:]
    limited = change(authed_client, current=API_PASSWORD)
    assert limited.status_code == 429 and "Retry-After" in limited.headers


def test_the_throttle_clears_after_the_delay(tmp_path: Path, clock: FakeClock) -> None:
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    with TestClient(create_app(settings, clock=clock), base_url="http://testserver") as client:
        client.post(f"{API}/auth/setup", json={"password": API_PASSWORD})
        for i in range(6):
            change(client, current=f"mauvais-mot-de-passe-{i}")
        clock.advance(60)
        assert change(client).status_code == 204


@pytest.mark.parametrize("weak", ["court", "motdepasse123", "azertyuiop12"])
def test_the_new_password_follows_the_rules_of_creation(
    authed_client: TestClient, weak: str
) -> None:
    response = change(authed_client, new=weak)
    assert response.status_code == 422
    assert authed_client.post(f"{API}/auth/lock").status_code == 204
    assert (
        authed_client.post(f"{API}/auth/unlock", json={"password": API_PASSWORD}).status_code == 204
    )


def test_the_new_password_must_differ(authed_client: TestClient) -> None:
    response = change(authed_client, new=API_PASSWORD)
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "new_password"


def test_other_sessions_are_closed(authed_client: TestClient, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    other_token = authed_client.post(f"{API}/auth/unlock", json={"password": API_PASSWORD})
    assert other_token.status_code == 204
    old_cookie = authed_client.cookies.get("finance_session")
    assert change(authed_client).status_code == 204
    new_cookie = authed_client.cookies.get("finance_session")
    assert new_cookie and new_cookie != old_cookie
    with TestClient(
        authed_client.app,
        base_url="http://testserver",
        cookies={"finance_session": old_cookie or ""},
    ) as stale:
        assert stale.get(f"{API}/accounts").status_code == 401
    assert settings.data_dir.exists()


def test_a_session_is_required(authed_client: TestClient) -> None:
    authed_client.cookies.clear()
    assert change(authed_client).status_code == 401


def test_the_new_session_cookie_is_hardened(authed_client: TestClient) -> None:
    response = change(authed_client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
