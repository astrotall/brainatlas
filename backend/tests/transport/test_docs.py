from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from neuroctivity.config import Settings
from neuroctivity.main import create_app
from tests.transport.openapi import assert_error

DOCS_URL = "/api/docs"
SCHEMA_URL = "/api/openapi.json"


def client_for_environment() -> TestClient:
    return TestClient(create_app())


@pytest.mark.parametrize("value", [None, "", "false", "0", "no"])
def test_does_not_serve_the_docs_unless_enabled(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is not None:
        monkeypatch.setenv("API_DOCS_ENABLED", value)

    client = client_for_environment()

    assert_error(client.get(DOCS_URL), HTTPStatus.NOT_FOUND, "not_found")
    assert client.get(SCHEMA_URL).status_code == HTTPStatus.OK


@pytest.mark.parametrize("value", ["true", "1", "TRUE"])
def test_serves_the_docs_locally_when_enabled(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("API_DOCS_ENABLED", value)

    assert client_for_environment().get(DOCS_URL).status_code == HTTPStatus.OK


def test_never_serves_the_docs_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_DOCS_ENABLED", "true")
    monkeypatch.setenv("VERCEL", "1")

    client = client_for_environment()

    assert_error(client.get(DOCS_URL), HTTPStatus.NOT_FOUND, "not_found")
    assert client.get(SCHEMA_URL).status_code == HTTPStatus.OK


@pytest.mark.parametrize("url", ["/docs", "/docs/oauth2-redirect", "/api/docs/oauth2-redirect", "/api/redoc"])
def test_exposes_no_other_documentation_route(url: str) -> None:
    client = TestClient(create_app(Settings(api_docs_enabled=True)))

    assert_error(client.get(url), HTTPStatus.NOT_FOUND, "not_found")


def test_refuses_to_start_on_an_unreadable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_DOCS_ENABLED", "banana")

    with pytest.raises(ValueError, match="api_docs_enabled"):
        create_app()


def test_the_flag_does_not_change_the_published_schema() -> None:
    enabled = create_app(Settings(api_docs_enabled=True)).openapi()
    disabled = create_app(Settings(api_docs_enabled=False)).openapi()

    assert enabled == disabled
