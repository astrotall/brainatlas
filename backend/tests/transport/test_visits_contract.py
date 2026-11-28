from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tests.transport.openapi import assert_documented, assert_error, node


@pytest.mark.parametrize(("method", "url"), [("post", "/api/visit"), ("get", "/api/stats")])
def test_a_planned_endpoint_answers_not_implemented(client: TestClient, method: str, url: str) -> None:
    response = client.request(method, url)

    assert_error(response, HTTPStatus.NOT_IMPLEMENTED, "not_implemented")
    assert_documented(response, url, method)
    assert "planned" in str(node("paths", url, method)["tags"])


def test_the_visit_endpoint_ignores_whatever_body_it_is_given(client: TestClient) -> None:
    response = client.post("/api/visit", content=b"not json", headers={"Content-Type": "text/plain"})

    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED


def test_the_visit_success_response_has_no_body() -> None:
    assert "content" not in node("paths", "/api/visit", "post", "responses", "204")


@pytest.mark.parametrize("counter", ["today", "total"])
def test_the_stats_counters_are_documented_as_non_negative_integers(counter: str) -> None:
    schema = node("components", "schemas", "VisitStats", "properties", counter)

    assert (schema["type"], schema["minimum"]) == ("integer", 0)
