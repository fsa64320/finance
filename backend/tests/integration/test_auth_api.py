"""T017 : création du mot de passe, sessions, délais après échecs, verrouillage (FR-028)."""

import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance.config import Settings
from finance.main import COOKIE_NAME, create_app
from tests.conftest import FakeClock

API = "/api/v1"
PASSWORD = "tulipe-bleue-47-horizon"  # noqa: S105 - valeur jetable des tests
OTHER = "autre-mot-de-passe-91"

MINUTE = 60.0
HOUR = 3600.0

MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client(tmp_path: Path, clock: FakeClock) -> Iterator[MakeClient]:
    opened: list[TestClient] = []

    def make(base_url: str = "http://testserver", data_dir: Path | None = None) -> TestClient:
        settings = Settings(data_dir=data_dir or tmp_path / "data", host="127.0.0.1", port=8000)
        client = TestClient(create_app(settings, clock=clock), base_url=base_url)
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: MakeClient) -> TestClient:
    return make_client()


def status(client: TestClient) -> str:
    return client.get(f"{API}/auth/status").json()["state"]


def setup(client: TestClient, password: str = PASSWORD) -> None:
    assert client.post(f"{API}/auth/setup", json={"password": password}).status_code == 204


def test_fresh_instance_is_uninitialized(client: TestClient) -> None:
    assert status(client) == "uninitialized"


def test_setup_opens_a_session_with_a_protected_cookie(client: TestClient, tmp_path: Path) -> None:
    response = client.post(f"{API}/auth/setup", json={"password": PASSWORD})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert f"{COOKIE_NAME}=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" not in cookie
    assert status(client) == "unlocked"
    database = tmp_path / "data" / "finance.db"
    assert database.exists()
    assert not database.read_bytes().startswith(b"SQLite format 3\x00")


def test_cookie_is_secure_over_https(make_client: MakeClient) -> None:
    secure_client = make_client("https://testserver")
    response = secure_client.post(f"{API}/auth/setup", json={"password": PASSWORD})
    assert response.status_code == 204
    assert "secure" in response.headers["set-cookie"].lower()


def test_setup_twice_is_refused(client: TestClient) -> None:
    setup(client)
    response = client.post(f"{API}/auth/setup", json={"password": OTHER})
    assert response.status_code == 409
    assert response.json()["code"] == "already_initialized"


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("court", "validation_error"),
        ("x" * 11, "validation_error"),
        ("x" * 129, "validation_error"),
        ("motdepasse123", "weak_password"),
        ("123456789012", "weak_password"),
    ],
)
def test_weak_passwords_are_refused_with_the_rule(
    client: TestClient, password: str, code: str
) -> None:
    response = client.post(f"{API}/auth/setup", json={"password": password})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == code
    assert body["details"][0]["field"] == "password"
    assert password not in response.text
    assert status(client) == "uninitialized"


def test_protected_route_needs_a_session(client: TestClient) -> None:
    setup(client)
    anonymous = TestClient(client.app, base_url="http://testserver")
    response = anonymous.post(f"{API}/auth/lock")
    assert response.status_code == 401
    assert response.json()["code"] == "session_required"


def test_unlock_with_wrong_password_is_refused(make_client: MakeClient) -> None:
    first = make_client()
    setup(first)
    first.post(f"{API}/auth/lock")
    response = first.post(f"{API}/auth/unlock", json={"password": OTHER})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert OTHER not in response.text
    assert status(first) == "locked"


def test_unlock_with_right_password_opens_a_session(client: TestClient) -> None:
    setup(client)
    client.post(f"{API}/auth/lock")
    assert status(client) == "locked"
    assert client.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204
    assert status(client) == "unlocked"


def test_unlock_before_setup_is_a_conflict(client: TestClient) -> None:
    response = client.post(f"{API}/auth/unlock", json={"password": PASSWORD})
    assert response.status_code == 409
    assert response.json()["code"] == "not_initialized"


def test_lock_clears_the_cookie_and_the_session(client: TestClient) -> None:
    setup(client)
    response = client.post(f"{API}/auth/lock")
    assert response.status_code == 204
    assert f'{COOKIE_NAME}=""' in response.headers["set-cookie"] or "max-age=0" in (
        response.headers["set-cookie"].lower()
    )
    assert status(client) == "locked"
    assert client.post(f"{API}/auth/lock").status_code == 401


def test_restart_locks_the_instance(make_client: MakeClient, tmp_path: Path) -> None:
    first = make_client(data_dir=tmp_path / "shared")
    setup(first)
    assert status(first) == "unlocked"
    cookie = first.cookies.get(COOKIE_NAME)
    restarted = make_client(data_dir=tmp_path / "shared")
    restarted.cookies.set(COOKIE_NAME, cookie or "")
    assert status(restarted) == "locked"
    assert restarted.post(f"{API}/auth/lock").status_code == 401
    assert restarted.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204


def test_five_failures_then_fifteen_seconds(client: TestClient, clock: FakeClock) -> None:
    setup(client)
    client.post(f"{API}/auth/lock")
    for _ in range(5):
        assert client.post(f"{API}/auth/unlock", json={"password": OTHER}).status_code == 401
    blocked = client.post(f"{API}/auth/unlock", json={"password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "15"
    assert blocked.json()["code"] == "too_many_attempts"
    clock.advance(15)
    assert client.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204


def test_delay_doubles_and_success_resets(client: TestClient, clock: FakeClock) -> None:
    setup(client)
    client.post(f"{API}/auth/lock")
    for _ in range(5):
        client.post(f"{API}/auth/unlock", json={"password": OTHER})
    clock.advance(15)
    assert client.post(f"{API}/auth/unlock", json={"password": OTHER}).status_code == 401
    blocked = client.post(f"{API}/auth/unlock", json={"password": OTHER})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "30"
    clock.advance(30)
    assert client.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204
    client.post(f"{API}/auth/lock")
    for _ in range(4):
        assert client.post(f"{API}/auth/unlock", json={"password": OTHER}).status_code == 401
    assert client.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204


def test_a_blocked_attempt_does_not_reveal_whether_the_password_is_right(
    client: TestClient,
) -> None:
    setup(client)
    client.post(f"{API}/auth/lock")
    for _ in range(5):
        client.post(f"{API}/auth/unlock", json={"password": OTHER})
    right = client.post(f"{API}/auth/unlock", json={"password": PASSWORD})
    wrong = client.post(f"{API}/auth/unlock", json={"password": OTHER})
    assert (right.status_code, right.json()) == (wrong.status_code, wrong.json())


def test_session_expires_after_thirty_idle_minutes_and_locks(
    client: TestClient, clock: FakeClock
) -> None:
    setup(client)
    clock.advance(29 * MINUTE)
    assert status(client) == "unlocked"
    clock.advance(31 * MINUTE)
    assert status(client) == "locked"
    assert client.post(f"{API}/auth/lock").status_code == 401
    assert client.post(f"{API}/auth/unlock", json={"password": PASSWORD}).status_code == 204


def test_activity_keeps_the_session_alive(client: TestClient, clock: FakeClock) -> None:
    setup(client)
    for _ in range(4):
        clock.advance(25 * MINUTE)
        assert status(client) == "unlocked"


def test_session_ends_twelve_hours_after_login_despite_activity(
    client: TestClient, clock: FakeClock
) -> None:
    setup(client)
    for _ in range(40):
        clock.advance(20 * MINUTE)
        if status(client) == "locked":
            break
    assert 11 * HOUR <= clock.now - 1000.0 <= 12 * HOUR + 20 * MINUTE
    assert status(client) == "locked"


def test_password_never_reaches_the_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        setup(client)
        client.post(f"{API}/auth/lock")
        client.post(f"{API}/auth/unlock", json={"password": OTHER})
        client.post(f"{API}/auth/setup", json={"password": "court"})
    assert PASSWORD not in caplog.text
    assert OTHER not in caplog.text


def test_malformed_body_uses_the_error_format(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/setup", content=b"pas du json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert set(response.json()) >= {"code", "message"}


def test_db_session_dependency_serves_only_unlocked_sessions(client: TestClient) -> None:
    from fastapi import Depends
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from finance.api.deps import get_db_session

    def probe(session: Session = Depends(get_db_session)) -> dict[str, int]:
        count = session.execute(text("SELECT count(*) FROM account")).scalar_one()
        return {"accounts": int(count)}

    client.app.add_api_route(f"{API}/_probe", probe)  # type: ignore[attr-defined]
    assert client.get(f"{API}/_probe").status_code == 401
    setup(client)
    assert client.get(f"{API}/_probe").json() == {"accounts": 0}
    client.post(f"{API}/auth/lock")
    assert client.get(f"{API}/_probe").status_code == 401
