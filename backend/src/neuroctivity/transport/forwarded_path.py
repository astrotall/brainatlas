from urllib.parse import quote, unquote

from starlette.types import ASGIApp, Receive, Scope, Send

API_PREFIX = "/api"
FORWARDED_PATH_PARAM = "__path"
REWRITE_PARAM = "__api_path"
RESERVED_PARAMS = frozenset({FORWARDED_PATH_PARAM, REWRITE_PARAM})
FUNCTION_PATHS = frozenset({"/api/index", "/api/index.py"})
QUERY_SEPARATOR = b"&"
QUERY_ENCODING = "latin-1"


def split_forwarded_path(query: bytes) -> tuple[str | None, bytes]:
    forwarded: str | None = None
    kept: list[bytes] = []
    for segment in query.split(QUERY_SEPARATOR):
        raw_name, _, raw_value = segment.partition(b"=")
        name = unquote(raw_name.decode(QUERY_ENCODING))
        if name not in RESERVED_PARAMS:
            kept.append(segment)
        elif name == FORWARDED_PATH_PARAM and forwarded is None:
            forwarded = unquote(raw_value.decode(QUERY_ENCODING))
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
