import json
from collections.abc import Mapping
from functools import cache
from http import HTTPStatus
from pathlib import Path

import httpx2
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012, Schema

SCHEMA_PATH = Path(__file__).resolve().parents[3] / ".claude" / "backend" / "openapi.json"
SCHEMA_URI = "urn:neuroctivity:openapi"
JSON_MEDIA_TYPE = "application/json"


@cache
def committed_schema() -> Schema:
    contents: Schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return contents


def node(*keys: str) -> Mapping[str, object]:
    current: object = committed_schema()
    for key in keys:
        assert isinstance(current, Mapping)
        current = current[key]
    assert isinstance(current, Mapping)
    return current


def pointer(*keys: str) -> str:
    return "/".join(key.replace("~", "~0").replace("/", "~1") for key in keys)


def schema_errors(instance: object, *keys: str) -> list[str]:
    registry: Registry[Schema] = Registry()
    resource: Resource[Schema] = Resource.from_contents(committed_schema(), default_specification=DRAFT202012)
    validator = Draft202012Validator(
        {"$ref": f"{SCHEMA_URI}#/{pointer(*keys)}"},
        registry=registry.with_resources([(SCHEMA_URI, resource)]),
        format_checker=FormatChecker(),
    )
    return [error.message for error in validator.iter_errors(instance)]


def declared_statuses(path: str, method: str) -> set[int]:
    return {int(status) for status in node("paths", path, method, "responses")}


def assert_documented(response: httpx2.Response, path: str, method: str) -> None:
    assert response.status_code in declared_statuses(path, method), response.text
    status = str(response.status_code)
    if "content" not in node("paths", path, method, "responses", status):
        assert response.content == b""
        return
    assert response.headers["content-type"] == JSON_MEDIA_TYPE
    keys = ("paths", path, method, "responses", status, "content", JSON_MEDIA_TYPE, "schema")
    assert schema_errors(response.json(), *keys) == []


def assert_error(response: httpx2.Response, status: HTTPStatus, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == JSON_MEDIA_TYPE
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    body = response.json()
    assert schema_errors(body, "components", "schemas", "ErrorResponse") == []
    assert body["error"]["code"] == code


def field_reasons(response: httpx2.Response) -> list[tuple[str, str]]:
    assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, "validation_failed")
    return [(entry["field"], entry["reason"]) for entry in response.json()["error"]["fields"]]
