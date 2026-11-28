import pytest

from tests.transport.openapi import declared_statuses, node

SCHEMAS = ("components", "schemas")


@pytest.mark.parametrize(
    ("schema", "field", "limits"),
    [
        ("CreateReviewRequest", "rating", {"type": "integer", "minimum": 1, "maximum": 5}),
        ("CreateReviewRequest", "text", {"type": "string", "minLength": 10, "maxLength": 1000}),
        ("CreateReviewRequest", "turnstileToken", {"type": "string", "minLength": 1, "maxLength": 2048}),
        ("Review", "rating", {"type": "integer", "minimum": 1, "maximum": 5}),
    ],
)
def test_publishes_the_limits_of_a_field(schema: str, field: str, limits: dict[str, object]) -> None:
    published = node(*SCHEMAS, schema, "properties", field)

    assert {key: published[key] for key in limits} == limits


def test_publishes_the_languages_as_an_enum() -> None:
    assert node(*SCHEMAS, "Language")["enum"] == ["ru", "en"]


def test_publishes_exactly_the_stable_error_codes() -> None:
    assert node(*SCHEMAS, "ErrorCode")["enum"] == [
        "validation_failed",
        "turnstile_failed",
        "rate_limited",
        "not_found",
        "method_not_allowed",
        "service_unavailable",
        "not_implemented",
        "internal",
    ]


def test_publishes_the_list_query_limits() -> None:
    parameters = node("paths", "/api/reviews")["get"]
    assert isinstance(parameters, dict)
    by_name = {parameter["name"]: parameter for parameter in parameters["parameters"]}

    assert by_name["lang"]["required"] is True
    assert by_name["limit"]["required"] is False
    assert {key: by_name["limit"]["schema"][key] for key in ("minimum", "maximum", "default")} == {
        "minimum": 1,
        "maximum": 100,
        "default": 50,
    }


@pytest.mark.parametrize(
    ("path", "method", "statuses"),
    [
        ("/api/health", "get", {200, 500}),
        ("/api/reviews", "get", {200, 422, 500, 501, 503}),
        ("/api/reviews", "post", {202, 403, 422, 429, 500, 501, 503}),
        ("/api/visit", "post", {204, 429, 500, 501, 503}),
        ("/api/stats", "get", {200, 500, 501, 503}),
    ],
)
def test_declares_every_status_of_an_operation(path: str, method: str, statuses: set[int]) -> None:
    assert declared_statuses(path, method) == statuses


def test_documents_retry_after_on_the_rate_limit_response() -> None:
    headers = node("paths", "/api/reviews", "post", "responses", "429", "headers")

    assert "Retry-After" in headers


def test_no_longer_publishes_the_default_framework_error_shape() -> None:
    assert "HTTPValidationError" not in node(*SCHEMAS)
