"""T018 : les routeurs montés respectent le contrat `contracts/openapi.yaml`.

`IMPLEMENTED_TAGS` grandit à chaque histoire ; la dernière tâche (T141) y mettra tous les tags.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI

from finance.config import Settings
from finance.main import create_app

CONTRACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-wealth-dashboard-foundation"
    / "contracts"
    / "openapi.yaml"
)
IMPLEMENTED_TAGS = {"auth", "accounts", "instruments", "transactions"}
# Opérations du contrat reportées à une tâche ultérieure ; T141 vide cette liste.
DEFERRED_OPERATIONS = {
    ("POST", "/api/v1/auth/change-password"),  # T139 (US5, FR-033)
    ("POST", "/api/v1/instruments/{instrumentId}/ticker-suggestions"),  # T110 (US4)
}
METHODS = {"get", "post", "put", "patch", "delete"}

Operation = dict[str, Any]


def prefix(contract: dict[str, Any]) -> str:
    return str(contract["servers"][0]["url"]).rstrip("/")


def operations(document: dict[str, Any], path_prefix: str = "") -> dict[tuple[str, str], Operation]:
    found: dict[tuple[str, str], Operation] = {}
    for path, item in document["paths"].items():
        for method, operation in item.items():
            if method in METHODS:
                found[(method.upper(), path_prefix + path)] = operation
    return found


def only_implemented(ops: dict[tuple[str, str], Operation]) -> dict[tuple[str, str], Operation]:
    return {
        key: op
        for key, op in ops.items()
        if IMPLEMENTED_TAGS & set(op.get("tags", [])) and key not in DEFERRED_OPERATIONS
    }


def resolve(document: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        node: Any = document
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def simplified(schema: dict[str, Any]) -> dict[str, Any]:
    """Ramène un schéma optionnel ou nullable (`anyOf` avec null, `type: [x, null]`) à sa base."""
    options = [o for o in schema.get("anyOf", []) if o.get("type") != "null"]
    if len(options) == 1:
        schema = {**{k: v for k, v in schema.items() if k != "anyOf"}, **options[0]}
    kind = schema.get("type")
    if isinstance(kind, list):
        remaining = [k for k in kind if k != "null"]
        schema = {**schema, "type": remaining[0] if len(remaining) == 1 else remaining}
    return schema


def body_schema(document: dict[str, Any], operation: Operation) -> dict[str, Any] | None:
    body = operation.get("requestBody")
    if body is None:
        return None
    return resolve(document, body["content"]["application/json"]["schema"])


def requires_session(document: dict[str, Any], operation: Operation) -> bool:
    security = operation.get("security", document.get("security", []))
    return bool(security)


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> FastAPI:
    settings = Settings(data_dir=tmp_path_factory.mktemp("data"), host="127.0.0.1", port=8000)
    return create_app(settings)


@pytest.fixture(scope="module")
def served(app: FastAPI) -> dict[str, Any]:
    return app.openapi()


def test_implemented_tags_exist_in_the_contract(contract: dict[str, Any]) -> None:
    declared = {tag["name"] for tag in contract["tags"]}
    assert declared >= IMPLEMENTED_TAGS


def test_deferred_operations_are_in_the_contract_but_not_served(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    assert set(operations(contract, prefix(contract))) >= DEFERRED_OPERATIONS
    assert not DEFERRED_OPERATIONS & set(operations(served))


def test_paths_and_methods_match_the_contract(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    expected = set(only_implemented(operations(contract, prefix(contract))))
    actual = set(only_implemented(operations(served)))
    assert actual == expected


def test_declared_status_codes_match_the_contract(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    expected = only_implemented(operations(contract, prefix(contract)))
    actual = operations(served)
    for key, operation in expected.items():
        assert set(actual[key]["responses"]) == set(operation["responses"]), key


def test_request_constraints_match_the_contract(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    expected = only_implemented(operations(contract, prefix(contract)))
    actual = operations(served)
    for key, operation in expected.items():
        wanted = body_schema(contract, operation)
        got = body_schema(served, actual[key])
        assert (wanted is None) == (got is None), key
        if wanted is None or got is None:
            continue
        assert set(got.get("required", [])) == set(wanted.get("required", [])), key
        for name, spec in wanted["properties"].items():
            for constraint in ("minLength", "maxLength", "type"):
                assert simplified(got["properties"][name]).get(constraint) == simplified(spec).get(
                    constraint
                ), (key, name, constraint)


def test_public_and_protected_operations_match_the_contract(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    expected = only_implemented(operations(contract, prefix(contract)))
    actual = operations(served)
    for key, operation in expected.items():
        assert requires_session(served, actual[key]) == requires_session(contract, operation), key


def test_session_cookie_scheme_matches_the_contract(
    contract: dict[str, Any], served: dict[str, Any]
) -> None:
    wanted = contract["components"]["securitySchemes"]["sessionCookie"]
    got = served["components"]["securitySchemes"]["sessionCookie"]
    assert (got["type"], got["in"], got["name"]) == (wanted["type"], wanted["in"], wanted["name"])


def test_contract_has_no_operation_without_a_tag_we_track(contract: dict[str, Any]) -> None:
    """Garde : une opération sans tag échapperait à la vérification."""
    untagged = [key for key, op in operations(contract).items() if not op.get("tags")]
    assert untagged == []
