from collections.abc import Mapping, Sequence
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import iter_route_contexts
from starlette.exceptions import HTTPException
from starlette.routing import compile_path

from neuroctivity.transport.errors import (
    ALLOW_HEADER,
    ErrorCode,
    FieldError,
    FieldReason,
    RouteNotImplementedError,
    error_response,
    field_error,
)

MAX_FIELD_ERRORS = 20
MAX_FIELD_NAME_LENGTH = 64
BODY_FIELD = "body"
METHOD_SEPARATOR = ", "

REASONS_BY_ERROR_TYPE: Mapping[str, FieldReason] = {
    "missing": FieldReason.MISSING,
    "extra_forbidden": FieldReason.UNKNOWN_FIELD,
    "string_too_short": FieldReason.TOO_SHORT,
    "string_too_long": FieldReason.TOO_LONG,
    "too_short": FieldReason.TOO_SHORT,
    "too_long": FieldReason.TOO_LONG,
}


def field_name(location: Sequence[object]) -> str:
    source, *parts = location
    if not parts or isinstance(parts[0], int):
        return str(source)
    return ".".join(str(part) for part in parts)[:MAX_FIELD_NAME_LENGTH]


def to_field_error(kind: str, location: Sequence[object]) -> FieldError:
    return field_error(field_name(location), REASONS_BY_ERROR_TYPE.get(kind, FieldReason.INVALID))


def handle_validation_error(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    fields = [to_field_error(issue["type"], issue["loc"]) for issue in error.errors()[:MAX_FIELD_ERRORS]]
    return error_response(ErrorCode.VALIDATION_FAILED, fields)


def allowed_methods(request: Request) -> str:
    methods: set[str] = set()
    for route in iter_route_contexts(request.app.routes):
        if route.path is not None and compile_path(route.path)[0].match(request.scope["path"]):
            methods.update(route.methods or ())
    if "GET" in methods:
        methods.add("HEAD")
    return METHOD_SEPARATOR.join(sorted(methods))


def handle_http_error(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, HTTPException):
        raise error
    if error.status_code == HTTPStatus.NOT_FOUND:
        return error_response(ErrorCode.NOT_FOUND)
    if error.status_code == HTTPStatus.METHOD_NOT_ALLOWED:
        return error_response(ErrorCode.METHOD_NOT_ALLOWED, headers={ALLOW_HEADER: allowed_methods(request)})
    if error.status_code == HTTPStatus.BAD_REQUEST:
        return error_response(ErrorCode.VALIDATION_FAILED, [field_error(BODY_FIELD, FieldReason.INVALID)])
    return error_response(ErrorCode.INTERNAL)


def handle_not_implemented(_request: Request, _error: Exception) -> JSONResponse:
    return error_response(ErrorCode.NOT_IMPLEMENTED)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RouteNotImplementedError, handle_not_implemented)
