import logging
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse

from neuroctivity.config import Settings
from neuroctivity.main import create_app
from tests.transport.openapi import assert_error

PRIVATE_TEXT = "private-review-text"
CACHED = "public, s-maxage=60, stale-while-revalidate=300"


class Strict(BaseModel):
    number: int


def failing_app() -> FastAPI:
    app = create_app(Settings())

    def explode() -> None:
        raise RuntimeError(PRIVATE_TEXT)

    def leak_invalid_response() -> Strict:
        return Strict.model_validate({"number": PRIVATE_TEXT})

    def teapot() -> None:
        raise HTTPException(status_code=HTTPStatus.IM_A_TEAPOT, detail=PRIVATE_TEXT)

    def break_midway() -> StreamingResponse:
        def chunks() -> Iterator[bytes]:
            yield b"partial"
            raise RuntimeError(PRIVATE_TEXT)

        return StreamingResponse(chunks())

    def cached() -> JSONResponse:
        return JSONResponse({}, headers={"Cache-Control": CACHED})

    app.get("/api/cached")(cached)
    app.get("/api/explode")(explode)
    app.get("/api/invalid-response")(leak_invalid_response)
    app.get("/api/teapot")(teapot)
    app.get("/api/midway")(break_midway)
    return app


@pytest.mark.parametrize(
    "url",
    [
        "/api",
        "/api/",
        "/api/unknown",
        "/api/health/",
        "/api/health/extra",
        "/api/HEALTH",
        "/api//health",
        "/api/%2e%2e/health",
        "/api/<script>",
        "/",
    ],
)
@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_an_unknown_path_answers_the_not_found_envelope(client: TestClient, method: str, url: str) -> None:
    response = client.request(method, url, follow_redirects=False)

    assert_error(response, HTTPStatus.NOT_FOUND, "not_found")
    assert response.json() == {"error": {"code": "not_found", "message": "Not found"}}


@pytest.mark.parametrize(
    ("method", "url", "allowed"),
    [
        ("POST", "/api/health", "GET, HEAD"),
        ("DELETE", "/api/health", "GET, HEAD"),
        ("PUT", "/api/reviews", "GET, HEAD, POST"),
        ("OPTIONS", "/api/reviews", "GET, HEAD, POST"),
        ("GET", "/api/visit", "POST"),
        ("HEAD", "/api/visit", "POST"),
        ("POST", "/api/stats", "GET, HEAD"),
        ("POST", "/api/openapi.json", "GET, HEAD"),
        ("PROPFIND", "/api/health", "GET, HEAD"),
    ],
)
def test_a_wrong_method_lists_every_allowed_method(
    client: TestClient, method: str, url: str, allowed: str
) -> None:
    response = client.request(method, url)

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert response.headers["allow"] == allowed
    if method != "HEAD":
        assert_error(response, HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")


@pytest.mark.parametrize(
    "url",
    ["/api/health", "/api/openapi.json", "/api/reviews?lang=ru", "/api/reviews", "/api/stats", "/api/nope"],
)
def test_head_answers_like_get_without_a_body(client: TestClient, url: str) -> None:
    get = client.get(url)
    head = client.head(url)

    assert head.status_code == get.status_code
    assert head.content == b""
    assert head.headers["content-length"] == str(len(get.content))
    assert head.headers["cache-control"] == get.headers["cache-control"]
    assert head.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("url", ["/api/explode", "/api/invalid-response"])
def test_an_unhandled_error_answers_the_internal_envelope_and_logs_no_values(
    url: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = TestClient(failing_app())

    with caplog.at_level(logging.DEBUG):
        response = client.get(url)

    assert_error(response, HTTPStatus.INTERNAL_SERVER_ERROR, "internal")
    assert response.json() == {"error": {"code": "internal", "message": "Internal error"}}
    assert "unhandled_error" in caplog.text
    assert "RedactedError" in caplog.text
    assert PRIVATE_TEXT not in caplog.text


def test_an_unexpected_http_error_hides_its_detail() -> None:
    response = TestClient(failing_app()).get("/api/teapot")

    assert_error(response, HTTPStatus.INTERNAL_SERVER_ERROR, "internal")
    assert PRIVATE_TEXT not in response.text


def test_an_error_after_the_response_started_sends_no_second_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(failing_app(), raise_server_exceptions=False)

    response = client.get("/api/midway")

    assert response.status_code == HTTPStatus.OK
    assert response.content == b"partial"
    assert "unhandled_error" in caplog.text
    assert PRIVATE_TEXT not in caplog.text


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_keeps_a_cache_policy_that_a_route_sets_itself(method: str) -> None:
    response = TestClient(failing_app()).request(method, "/api/cached")

    assert response.headers["cache-control"] == CACHED
    assert response.headers["x-content-type-options"] == "nosniff"
