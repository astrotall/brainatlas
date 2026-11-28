import runpy
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from neuroctivity.transport import health

HEALTH_URL = "/api/health"
ENTRYPOINT = Path(__file__).resolve().parents[3] / "api" / "index.py"


def test_health_answers_ok_with_exactly_the_documented_body(client: TestClient) -> None:
    response = client.get(HEALTH_URL)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_health_rejects_a_write_method(client: TestClient) -> None:
    assert client.post(HEALTH_URL).status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_health_is_served_only_under_the_api_prefix(client: TestClient) -> None:
    assert client.get("/health").status_code == HTTPStatus.NOT_FOUND


def test_the_schema_lives_under_the_api_prefix(client: TestClient) -> None:
    schema = client.get("/api/openapi.json")

    assert schema.status_code == HTTPStatus.OK
    assert HEALTH_URL in schema.json()["paths"]
    assert client.get("/openapi.json").status_code == HTTPStatus.NOT_FOUND


def test_unwired_use_case_fails_loudly_instead_of_answering() -> None:
    app = FastAPI()
    app.include_router(health.router, prefix="/api")

    with pytest.raises(TypeError, match=health.CHECK_HEALTH_STATE):
        TestClient(app).get(HEALTH_URL)


def test_vercel_entrypoint_exposes_the_application_as_app() -> None:
    namespace = runpy.run_path(str(ENTRYPOINT))

    assert isinstance(namespace["app"], FastAPI)
    assert TestClient(namespace["app"]).get(HEALTH_URL).json() == {"status": "ok"}
