from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from neuroctivity.transport.forwarded_path import split_forwarded_path
from tests.transport.openapi import assert_error

SUBMISSION = {"rating": 5, "text": "A clear course.", "lang": "en", "turnstileToken": "token"}


@pytest.mark.parametrize(
    ("query", "forwarded", "kept"),
    [
        (b"", None, b""),
        (b"lang=ru", None, b"lang=ru"),
        (b"__path=health", "health", b""),
        (b"__path=", "", b""),
        (b"__path", "", b""),
        (b"lang=ru&limit=5&__path=reviews", "reviews", b"lang=ru&limit=5"),
        (b"__path=a%2Fb", "a/b", b""),
        (b"%5F%5Fpath=health", "health", b""),
        (b"__path=reviews&__path=health", "health", b""),
        (b"lang=ru&lang=en&__path=reviews", "reviews", b"lang=ru&lang=en"),
        (b"__paths=health&x__path=health", None, b"__paths=health&x__path=health"),
        (b"a=1&&b=%26", None, b"a=1&&b=%26"),
        (b"__path=%ff", "�", b""),
    ],
)
def test_separates_the_forwarded_path_and_keeps_the_rest_untouched(
    query: bytes, forwarded: str | None, kept: bytes
) -> None:
    assert split_forwarded_path(query) == (forwarded, kept)


@pytest.mark.parametrize("function", ["/api/index", "/api/index.py"])
def test_restores_the_path_when_the_function_sees_the_rewrite_destination(
    client: TestClient, function: str
) -> None:
    response = client.get(f"{function}?__path=health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("/api/index?__path=reviews&lang=ru", HTTPStatus.NOT_IMPLEMENTED),
        ("/api/index?lang=ru&limit=5&__path=reviews", HTTPStatus.NOT_IMPLEMENTED),
        ("/api/index?__path=stats", HTTPStatus.NOT_IMPLEMENTED),
        ("/api/index?__path=openapi.json", HTTPStatus.OK),
    ],
)
def test_keeps_the_original_query_after_restoring_the_path(
    client: TestClient, url: str, status: HTTPStatus
) -> None:
    assert client.get(url).status_code == status


def test_restores_the_path_of_a_write_with_its_body(client: TestClient) -> None:
    response = client.post("/api/index?__path=reviews", json=SUBMISSION)

    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED


def test_restores_the_path_before_choosing_the_allowed_methods(client: TestClient) -> None:
    response = client.post("/api/index?__path=health")

    assert_error(response, HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")
    assert response.headers["allow"] == "GET, HEAD"


def test_restores_the_path_for_head(client: TestClient) -> None:
    response = client.head("/api/index?__path=health")

    assert response.status_code == HTTPStatus.OK
    assert response.content == b""


@pytest.mark.parametrize(
    "url",
    [
        "/api/index",
        "/api/index?__path=",
        "/api/index?__path=index",
        "/api/index?__path=%3Apath*",
        "/api/index?__path=unknown%2Fdeep",
        "/api/index?__path=..%2F..%2Fetc%2Fpasswd",
        "/api/index?__path=%2Fhealth",
        "/api/index?__path=health%3Fx%3D1",
        "/api/index?__path=%00",
    ],
)
def test_answers_not_found_for_a_forwarded_path_with_no_route(client: TestClient, url: str) -> None:
    assert_error(client.get(url), HTTPStatus.NOT_FOUND, "not_found")


@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("/api/health?__path=health", HTTPStatus.OK),
        ("/api/health?__path=reviews", HTTPStatus.OK),
        ("/api/reviews?lang=ru&__path=reviews", HTTPStatus.NOT_IMPLEMENTED),
        ("/api/unknown?__path=health", HTTPStatus.NOT_FOUND),
    ],
)
def test_ignores_and_strips_the_parameter_when_the_function_sees_the_original_path(
    client: TestClient, url: str, status: HTTPStatus
) -> None:
    assert client.get(url).status_code == status
