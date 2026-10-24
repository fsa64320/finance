"""T033 : en-têtes de sécurité, contrôle de l'origine, taille maximale des requêtes."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance.config import Settings
from finance.main import create_app

API = "/api/v1"


def build(tmp_path: Path, allowed_origins: tuple[str, ...] = ()) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data", host="127.0.0.1", port=8000, allowed_origins=allowed_origins
    )
    return TestClient(create_app(settings), base_url="http://testserver")


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with build(tmp_path) as opened:
        yield opened


def test_security_headers_on_api_responses(client: TestClient) -> None:
    headers = client.get(f"{API}/auth/status").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert "no-store" in headers["cache-control"]
    csp = headers["content-security-policy"]
    for directive in (
        "default-src 'self'",
        "script-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "connect-src 'self'",
    ):
        assert directive in csp


def test_security_headers_also_on_errors(client: TestClient) -> None:
    response = client.get("/inconnu")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


def test_interactive_docs_and_schema_are_not_exposed(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json", f"{API}/openapi.json", f"{API}/docs"):
        assert client.get(path).status_code == 404


def test_cross_site_write_is_refused(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/unlock",
        json={"password": "x"},
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_origin"


def test_same_origin_write_is_allowed(client: TestClient) -> None:
    response = client.post(
        f"{API}/auth/unlock", json={"password": "x"}, headers={"origin": "http://testserver"}
    )
    assert response.status_code != 403


def test_write_without_origin_is_allowed_for_non_browser_clients(client: TestClient) -> None:
    assert client.post(f"{API}/auth/unlock", json={"password": "x"}).status_code != 403


def test_reads_ignore_the_origin_header(client: TestClient) -> None:
    response = client.get(f"{API}/auth/status", headers={"origin": "https://evil.example"})
    assert response.status_code == 200


def test_configured_origin_is_accepted_behind_a_proxy(tmp_path: Path) -> None:
    with build(tmp_path, allowed_origins=("https://finance.example.org",)) as proxied:
        response = proxied.post(
            f"{API}/auth/unlock",
            json={"password": "x"},
            headers={"origin": "https://finance.example.org"},
        )
        assert response.status_code != 403


def test_oversized_json_body_is_refused(client: TestClient) -> None:
    body = b'{"password": "' + b"a" * (1024 * 1024 + 10) + b'"}'
    response = client.post(
        f"{API}/auth/setup", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_body_just_under_the_limit_is_read(client: TestClient) -> None:
    body = b'{"password": "' + b"a" * 2000 + b'"}'
    response = client.post(
        f"{API}/auth/setup", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 422  # lu, puis refusé par la règle de longueur
