import asyncio
import json
import logging

import httpx
import pytest
from upstash_redis.errors import UpstashError

from neuroctivity.application.errors import DependencyUnavailableError
from neuroctivity.infrastructure.redis_scripts import CLAIM_TOKEN
from neuroctivity.infrastructure.upstash import BoundedScriptRunner, Evaluate, upstash_evaluate
from tests.logs import logged_text

PROVIDER_MESSAGE = "WRONGPASS invalid password for prod:review:secret"


def failing(error: Exception) -> Evaluate:
    async def evaluate(source: str, keys: list[str], args: list[str]) -> object:
        del source, keys, args
        raise error

    return evaluate


def answering(answer: object, calls: list[tuple[str, list[str], list[str]]]) -> Evaluate:
    async def evaluate(source: str, keys: list[str], args: list[str]) -> object:
        calls.append((source, keys, args))
        return answer

    return evaluate


def slow() -> Evaluate:
    async def evaluate(source: str, keys: list[str], args: list[str]) -> object:
        del source, keys, args
        await asyncio.sleep(10)
        return 1

    return evaluate


def test_passes_the_script_keys_and_arguments_through() -> None:
    calls: list[tuple[str, list[str], list[str]]] = []
    runner = BoundedScriptRunner(answering(1, calls), timeout_seconds=1)

    assert asyncio.run(runner.run(CLAIM_TOKEN, ("k",), ("300",))) == 1
    assert calls == [(CLAIM_TOKEN.source, ["k"], ["300"])]


@pytest.mark.parametrize(
    "error",
    [
        UpstashError(PROVIDER_MESSAGE),
        httpx.ConnectError(PROVIDER_MESSAGE),
        httpx.ReadTimeout(PROVIDER_MESSAGE),
        OSError(PROVIDER_MESSAGE),
        json.JSONDecodeError(PROVIDER_MESSAGE, "doc", 0),
        KeyError(PROVIDER_MESSAGE),
        TypeError(PROVIDER_MESSAGE),
    ],
)
def test_a_provider_failure_becomes_unavailable_without_logging_its_message(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    runner = BoundedScriptRunner(failing(error), timeout_seconds=1)

    with caplog.at_level(logging.DEBUG), pytest.raises(DependencyUnavailableError) as raised:
        asyncio.run(runner.run(CLAIM_TOKEN, ("k",), ("300",)))

    assert raised.value.__cause__ is None
    assert "redis_unavailable" in caplog.text
    assert PROVIDER_MESSAGE not in logged_text(caplog)
    assert "secret" not in logged_text(caplog)


def test_a_hanging_call_is_cut_off_at_the_timeout() -> None:
    runner = BoundedScriptRunner(slow(), timeout_seconds=0.01)

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(runner.run(CLAIM_TOKEN, ("k",), ("300",)))


def test_a_programming_error_is_not_disguised_as_an_outage() -> None:
    runner = BoundedScriptRunner(failing(ZeroDivisionError()), timeout_seconds=1)

    with pytest.raises(ZeroDivisionError):
        asyncio.run(runner.run(CLAIM_TOKEN, ("k",), ("300",)))


def test_builds_a_client_without_contacting_upstash() -> None:
    evaluate = upstash_evaluate("https://example.invalid", "token")

    assert callable(evaluate)
