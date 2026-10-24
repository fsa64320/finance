"""FR-028 : tous les endpoints, sauf /auth/*, exigent une session ouverte."""

import re

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import API

METHODS = ("get", "post", "put", "patch", "delete")
ID = "11111111-1111-4111-8111-111111111111"


def protected_operations(client: TestClient) -> list[tuple[str, str]]:
    paths = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    found = []
    for path, operations in paths.items():
        if path.startswith("/api/v1/auth/"):
            continue
        for method in METHODS:
            if method in operations:
                found.append((method.upper(), re.sub(r"\{[^}]+\}", ID, path)))
    return sorted(found)


def test_every_operation_is_listed(authed_client: TestClient) -> None:
    operations = protected_operations(authed_client)
    assert len(operations) >= 30
    assert ("POST", "/api/v1/data/restore") in operations
    assert ("GET", "/api/v1/data/export") in operations


def test_without_a_session_everything_is_refused(authed_client: TestClient) -> None:
    operations = protected_operations(authed_client)
    authed_client.cookies.clear()
    for method, path in operations:
        response = authed_client.request(method, path, json={})
        assert response.status_code == 401, (method, path, response.status_code)
        assert "set-cookie" not in response.headers


@pytest.mark.parametrize("cookie", ["", "jeton-invente", "x" * 500])
def test_a_forged_session_is_refused(authed_client: TestClient, cookie: str) -> None:
    operations = protected_operations(authed_client)
    authed_client.cookies.clear()
    authed_client.cookies.set("finance_session", cookie)
    for method, path in operations:
        assert authed_client.request(method, path, json={}).status_code == 401, (method, path)


def test_once_the_instance_is_locked_everything_is_refused(authed_client: TestClient) -> None:
    operations = protected_operations(authed_client)
    assert authed_client.post(f"{API}/auth/lock").status_code == 204
    for method, path in operations:
        response = authed_client.request(method, path, json={})
        assert response.status_code == 401, (method, path, response.status_code)
    assert authed_client.get(f"{API}/auth/status").json() == {"state": "locked"}


def test_the_status_endpoint_stays_public(authed_client: TestClient) -> None:
    authed_client.cookies.clear()
    assert authed_client.get(f"{API}/auth/status").status_code == 200
