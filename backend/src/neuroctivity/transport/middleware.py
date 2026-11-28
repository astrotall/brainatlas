import logging

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from neuroctivity.transport.errors import ErrorCode, FieldReason, error_response, field_error
from neuroctivity.transport.forwarded_path import RestoreForwardedPath

MAX_BODY_BYTES = 16 * 1024
BODY_FIELD = "body"

logger = logging.getLogger(__name__)


class RedactedError(Exception):
    pass


class ApplyResponseDefaults:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_defaults(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Cache-Control", "no-store")
                headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        await self._app(scope, receive, send_with_defaults)


class AnswerHeadAsGet:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self._app(scope, receive, send)
            return

        async def send_without_body(message: Message) -> None:
            if message["type"] == "http.response.body":
                message = {**message, "body": b""}
            await send(message)

        await self._app({**scope, "method": "GET"}, receive, send_without_body)


class ContainUnhandledErrors:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = False

        async def send_and_track(message: Message) -> None:
            nonlocal started
            started = True
            await send(message)

        try:
            await self._app(scope, receive, send_and_track)
        except Exception as error:
            redacted = RedactedError(type(error).__name__)
            logger.exception("unhandled_error", exc_info=(RedactedError, redacted, error.__traceback__))
            if not started:
                await error_response(ErrorCode.INTERNAL)(scope, receive, send)


class LimitBodySize:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                return
            body.extend(message.get("body", b""))
            if len(body) > self._max_bytes:
                too_long = field_error(BODY_FIELD, FieldReason.TOO_LONG)
                await error_response(ErrorCode.VALIDATION_FAILED, [too_long])(scope, receive, send)
                return
            more_body = message.get("more_body", False)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self._app(scope, replay, send)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(LimitBodySize, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(RestoreForwardedPath)
    app.add_middleware(ContainUnhandledErrors)
    app.add_middleware(AnswerHeadAsGet)
    app.add_middleware(ApplyResponseDefaults)
