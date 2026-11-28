import asyncio
import json
import logging
from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest

from neuroctivity.application.errors import DependencyUnavailableError, HumanCheckFailedError
from neuroctivity.infrastructure.turnstile import SITEVERIFY_URL, TurnstileVerifier
from tests.logs import logged_text

SECRET = "server-secret-value"
TOKEN = "client-token-value"
SITE = "neuroctivity.example"

Handler = Callable[[httpx.Request], httpx.Response]


def answering(body: object, status: int = 200) -> Handler:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return handle


def raising(error: Exception) -> Handler:
    def handle(_request: httpx.Request) -> httpx.Response:
        raise error

    return handle


def verify(handler: Handler, hostnames: tuple[str, ...] = ()) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    asyncio.run(TurnstileVerifier(client, SECRET, hostnames).verify(TOKEN))


def test_sends_the_secret_and_the_token_and_nothing_about_the_visitor() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True, "hostname": SITE})

    verify(handle)

    [request] = seen
    assert str(request.url) == SITEVERIFY_URL
    assert request.method == "POST"
    assert parse_qs(request.content.decode()) == {"secret": [SECRET], "response": [TOKEN]}


@pytest.mark.parametrize("hostnames", [(), (SITE,), ("other.example", SITE)])
def test_accepts_a_successful_answer_for_an_allowed_host(hostnames: tuple[str, ...]) -> None:
    verify(answering({"success": True, "hostname": SITE, "error-codes": []}), hostnames)


def test_accepts_the_test_secret_answer_when_no_hostname_is_configured() -> None:
    verify(answering({"success": True, "hostname": "example.com"}))


@pytest.mark.parametrize("body", [{"success": True, "hostname": "evil.example"}, {"success": True}])
def test_rejects_a_token_issued_for_another_host(body: object) -> None:
    with pytest.raises(HumanCheckFailedError):
        verify(answering(body), (SITE,))


@pytest.mark.parametrize(
    "codes",
    [
        ["invalid-input-response"],
        ["timeout-or-duplicate"],
        ["missing-input-response"],
        [],
        ["invalid-input-response", "timeout-or-duplicate"],
    ],
)
def test_a_bad_expired_or_reused_token_is_rejected(codes: list[str]) -> None:
    with pytest.raises(HumanCheckFailedError):
        verify(answering({"success": False, "error-codes": codes}))


@pytest.mark.parametrize(
    "codes",
    [
        ["invalid-input-secret"],
        ["missing-input-secret"],
        ["internal-error"],
        ["bad-request"],
        ["something-new"],
        ["timeout-or-duplicate", "internal-error"],
    ],
)
def test_a_provider_or_configuration_error_is_an_outage_not_the_visitors_fault(codes: list[str]) -> None:
    with pytest.raises(DependencyUnavailableError):
        verify(answering({"success": False, "error-codes": codes}))


@pytest.mark.parametrize(
    "handler",
    [
        raising(httpx.ConnectTimeout("slow")),
        raising(httpx.ReadTimeout("slow")),
        raising(httpx.ConnectError("down")),
        answering({"success": True}, status=500),
        answering({"success": True}, status=429),
        answering("not an object"),
        answering({"success": "true"}),
        answering({"success": 1}),
        answering({"error-codes": []}),
        answering({"success": True, "error-codes": "none"}),
        lambda _request: httpx.Response(200, content=b"<html>"),
    ],
)
def test_an_unreachable_or_malformed_provider_fails_closed_as_unavailable(handler: Handler) -> None:
    with pytest.raises(DependencyUnavailableError):
        verify(handler)


def test_never_logs_the_token_or_the_secret(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        for body in (
            {"success": False, "error-codes": ["invalid-input-response"]},
            {"success": False, "error-codes": ["internal-error"]},
        ):
            with pytest.raises((HumanCheckFailedError, DependencyUnavailableError)):
                verify(answering(body))

    logged = logged_text(caplog)
    assert TOKEN not in logged
    assert SECRET not in logged
    assert "invalid-input-response" in logged


def test_ignores_extra_fields_the_provider_may_add() -> None:
    verify(answering({"success": True, "hostname": SITE, "action": "x", "cdata": json.dumps({"a": 1})}))
