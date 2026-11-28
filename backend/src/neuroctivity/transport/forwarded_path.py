from urllib.parse import quote, unquote

from starlette.types import ASGIApp, Receive, Scope, Send

API_PREFIX = "/api"
FORWARDED_PATH_PARAM = "__path"
FUNCTION_PATHS = frozenset({"/api/index", "/api/index.py"})
QUERY_SEPARATOR = b"&"
QUERY_ENCODING = "latin-1"


def split_forwarded_path(query: bytes) -> tuple[str | None, bytes]:
    forwarded: str | None = None
    kept: list[bytes] = []
    for segment in query.split(QUERY_SEPARATOR):
        name, _, value = segment.partition(b"=")
        if unquote(name.decode(QUERY_ENCODING)) == FORWARDED_PATH_PARAM:
            forwarded = unquote(value.decode(QUERY_ENCODING))
        else:
            kept.append(segment)
    return forwarded, QUERY_SEPARATOR.join(kept)


class RestoreForwardedPath:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            forwarded, query = split_forwarded_path(scope["query_string"])
            if forwarded is not None:
                scope = {**scope, "query_string": query}
                if scope["path"] in FUNCTION_PATHS:
                    path = f"{API_PREFIX}/{forwarded}" if forwarded else API_PREFIX
                    scope |= {"path": path, "raw_path": quote(path).encode()}
        await self._app(scope, receive, send)
