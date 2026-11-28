import pytest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from neuroctivity.transport.forwarded_path import RestoreForwardedPath
from neuroctivity.transport.middleware import (
    AnswerHeadAsGet,
    ApplyResponseDefaults,
    ContainUnhandledErrors,
    LimitBodySize,
)

HTTP_SCOPE: Scope = {"type": "http", "method": "POST", "path": "/api/reviews", "headers": []}


class Recorder:
    def __init__(self) -> None:
        self.scopes: list[str] = []
        self.received: list[Message] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.scopes.append(scope["type"])
        if scope["type"] == "http":
            self.received.append(await receive())
            self.received.append(await receive())
        await send({"type": "done"})


def scripted(messages: list[Message]) -> Receive:
    queue = list(messages)

    async def receive() -> Message:
        return queue.pop(0)

    return receive


def collector(sent: list[Message]) -> Send:
    async def send(message: Message) -> None:
        sent.append(message)

    return send


def wrappers(app: ASGIApp) -> list[ASGIApp]:
    return [
        ApplyResponseDefaults(app),
        AnswerHeadAsGet(app),
        ContainUnhandledErrors(app),
        LimitBodySize(app, max_bytes=8),
        RestoreForwardedPath(app),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("index", range(5))
async def test_passes_a_lifespan_scope_straight_through(index: int) -> None:
    recorder = Recorder()
    sent: list[Message] = []

    await wrappers(recorder)[index]({"type": "lifespan"}, scripted([]), collector(sent))

    assert recorder.scopes == ["lifespan"]
    assert sent == [{"type": "done"}]


@pytest.mark.anyio
async def test_joins_a_chunked_body_and_then_forwards_the_disconnect() -> None:
    recorder = Recorder()
    receive = scripted(
        [
            {"type": "http.request", "body": b"abcd", "more_body": True},
            {"type": "http.request", "body": b"efgh", "more_body": False},
            {"type": "http.disconnect"},
        ]
    )

    await LimitBodySize(recorder, max_bytes=8)(HTTP_SCOPE, receive, collector([]))

    assert recorder.received == [
        {"type": "http.request", "body": b"abcdefgh", "more_body": False},
        {"type": "http.disconnect"},
    ]


@pytest.mark.anyio
async def test_stops_reading_a_chunked_body_as_soon_as_it_passes_the_limit() -> None:
    recorder = Recorder()
    sent: list[Message] = []
    receive = scripted(
        [
            {"type": "http.request", "body": b"abcd", "more_body": True},
            {"type": "http.request", "body": b"efghi", "more_body": True},
        ]
    )

    await LimitBodySize(recorder, max_bytes=8)(HTTP_SCOPE, receive, collector(sent))

    assert recorder.scopes == []
    assert sent[0]["status"] == 422


@pytest.mark.anyio
async def test_never_runs_the_application_for_a_client_that_left_mid_body() -> None:
    recorder = Recorder()
    sent: list[Message] = []
    receive = scripted(
        [{"type": "http.request", "body": b"ab", "more_body": True}, {"type": "http.disconnect"}]
    )

    await LimitBodySize(recorder, max_bytes=8)(HTTP_SCOPE, receive, collector(sent))

    assert recorder.scopes == []
    assert sent == []
