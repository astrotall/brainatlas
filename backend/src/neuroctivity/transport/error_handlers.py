import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import iter_route_contexts
from starlette.exceptions import HTTPException
from starlette.routing import compile_path

from neuroctivity.application.errors import (
    DependencyUnavailableError,
    HumanCheckFailedError,
    RateLimitedError,
)
from neuroctivity.domain.client import InvalidClientAddressError
from neuroctivity.domain.review import ReviewRuleError
from neuroctivity.transport.errors import (
    ALLOW_HEADER,
    RETRY_AFTER_HEADER,
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

logger = logging.getLogger(__name__)

REASONS_BY_ERROR_TYPE: Mapping[str, FieldReason] = {
    "missing": FieldReason.MISSING,
    "extra_forbidden": FieldReason.UNKNOWN_FIELD,
    "string_too_short": FieldReason.TOO_SHORT,
    "string_too_long": FieldReason.TOO_LONG,
    "too_short": FieldReason.TOO_SHORT,
    "too_long": FieldReason.TOO_LONG,
    FieldReason.LINKS_NOT_ALLOWED.value: FieldReason.LINKS_NOT_ALLOWED,
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


def handle_review_rule(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ReviewRuleError):
        raise error
    reason = FieldReason(error.violation.value)
    return error_response(ErrorCode.VALIDATION_FAILED, [field_error(error.field.value, reason)])


def handle_human_check_failed(_request: Request, _error: Exception) -> JSONResponse:
    return error_response(ErrorCode.TURNSTILE_FAILED)


def handle_rate_limited(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RateLimitedError):
        raise error
    return error_response(
        ErrorCode.RATE_LIMITED, headers={RETRY_AFTER_HEADER: str(error.retry_after_seconds)}
    )


def handle_unavailable(_request: Request, error: Exception) -> JSONResponse:
    dependency = error.dependency.value if isinstance(error, DependencyUnavailableError) else "client_address"
    logger.warning("service_unavailable", extra={"dependency": dependency})
    return error_response(ErrorCode.SERVICE_UNAVAILABLE)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RouteNotImplementedError, handle_not_implemented)
    app.add_exception_handler(ReviewRuleError, handle_review_rule)
    app.add_exception_handler(HumanCheckFailedError, handle_human_check_failed)
    app.add_exception_handler(RateLimitedError, handle_rate_limited)
    app.add_exception_handler(DependencyUnavailableError, handle_unavailable)
    app.add_exception_handler(InvalidClientAddressError, handle_unavailable)
