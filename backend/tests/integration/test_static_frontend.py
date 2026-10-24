"""Le frontend compilé est servi par le backend, avec repli sur index.html pour les routes."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance.config import Settings
from finance.main import create_app


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text("<!doctype html><title>Finance</title>", encoding="utf-8")
    (directory / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("hors du dossier", encoding="utf-8")
    return directory


@pytest.fixture
def client(tmp_path: Path, static_dir: Path) -> Iterator[TestClient]:
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    with TestClient(create_app(settings, static_dir=static_dir)) as opened:
        yield opened


def test_index_is_served_at_the_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Finance</title>" in response.text


def test_assets_are_served(client: TestClient) -> None:
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_client_side_routes_fall_back_to_index(client: TestClient) -> None:
    response = client.get("/comptes/abc")
    assert response.status_code == 200
    assert "<title>Finance</title>" in response.text


def test_unknown_api_paths_are_json_404_not_index(client: TestClient) -> None:
    response = client.get("/api/v1/inconnu")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("path", ["/../secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"])
def test_path_traversal_is_blocked(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert "hors du dossier" not in response.text


def test_without_a_build_the_api_still_works(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    with TestClient(create_app(settings, static_dir=tmp_path / "absent")) as opened:
        assert opened.get("/api/v1/auth/status").status_code == 200
        assert opened.get("/").status_code == 404
