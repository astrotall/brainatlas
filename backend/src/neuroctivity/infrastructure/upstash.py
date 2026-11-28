import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence

import httpx
from upstash_redis.asyncio import Redis
from upstash_redis.errors import UpstashError

from neuroctivity.application.errors import Dependency, DependencyUnavailableError
from neuroctivity.infrastructure.redis_scripts import Script

logger = logging.getLogger(__name__)

REDIS_FAILURES = (
    UpstashError,
    httpx.HTTPError,
    TimeoutError,
    OSError,
    json.JSONDecodeError,
    KeyError,
    TypeError,
)

Evaluate = Callable[[str, list[str], list[str]], Awaitable[object]]


def upstash_evaluate(url: str, token: str) -> Evaluate:
    redis = Redis(url=url, token=token, rest_retries=0, allow_telemetry=False, read_your_writes=False)

    async def evaluate(source: str, keys: list[str], args: list[str]) -> object:
        answer: object = await redis.eval(source, keys=keys, args=args)
        return answer

    return evaluate


class BoundedScriptRunner:
    def __init__(self, evaluate: Evaluate, timeout_seconds: float) -> None:
        self._evaluate = evaluate
        self._timeout_seconds = timeout_seconds

    async def run(self, script: Script, keys: Sequence[str], args: Sequence[str]) -> object:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._evaluate(script.source, list(keys), list(args))
        except REDIS_FAILURES as error:
            logger.warning("redis_unavailable", extra={"script": script.name, "error": type(error).__name__})
            raise DependencyUnavailableError(Dependency.STORE) from None
