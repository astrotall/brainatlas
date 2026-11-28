from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

RETRY_AFTER_HEADER = "Retry-After"
ALLOW_HEADER = "Allow"


class ErrorCode(StrEnum):
    VALIDATION_FAILED = "validation_failed"
    TURNSTILE_FAILED = "turnstile_failed"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    SERVICE_UNAVAILABLE = "service_unavailable"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL = "internal"


class FieldReason(StrEnum):
    MISSING = "missing"
    INVALID = "invalid"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    LINKS_NOT_ALLOWED = "links_not_allowed"
    UNKNOWN_FIELD = "unknown_field"


@dataclass(frozen=True, slots=True)
class ErrorKind:
    status: HTTPStatus
    message: str


ERROR_KINDS: Mapping[ErrorCode, ErrorKind] = {
    ErrorCode.VALIDATION_FAILED: ErrorKind(HTTPStatus.UNPROCESSABLE_ENTITY, "The request is invalid"),
    ErrorCode.TURNSTILE_FAILED: ErrorKind(HTTPStatus.FORBIDDEN, "The human check failed"),
    ErrorCode.RATE_LIMITED: ErrorKind(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests"),
    ErrorCode.NOT_FOUND: ErrorKind(HTTPStatus.NOT_FOUND, "Not found"),
    ErrorCode.METHOD_NOT_ALLOWED: ErrorKind(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed"),
    ErrorCode.SERVICE_UNAVAILABLE: ErrorKind(
        HTTPStatus.SERVICE_UNAVAILABLE, "The service is temporarily unavailable"
    ),
    ErrorCode.NOT_IMPLEMENTED: ErrorKind(HTTPStatus.NOT_IMPLEMENTED, "Not implemented yet"),
    ErrorCode.INTERNAL: ErrorKind(HTTPStatus.INTERNAL_SERVER_ERROR, "Internal error"),
}

FIELD_MESSAGES: Mapping[FieldReason, str] = {
    FieldReason.MISSING: "This field is required",
    FieldReason.INVALID: "This value is invalid",
    FieldReason.TOO_SHORT: "This value is too short",
    FieldReason.TOO_LONG: "This value is too long",
    FieldReason.LINKS_NOT_ALLOWED: "Links are not allowed",
    FieldReason.UNKNOWN_FIELD: "This field is not accepted",
}


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    message: str
    reason: FieldReason


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode
    message: str
    fields: list[FieldError] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorDetail


class RouteNotImplementedError(Exception):
    pass


def field_error(name: str, reason: FieldReason) -> FieldError:
    return FieldError(field=name, message=FIELD_MESSAGES[reason], reason=reason)


def error_response(
    code: ErrorCode,
    fields: Sequence[FieldError] = (),
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    kind = ERROR_KINDS[code]
    body = ErrorResponse(error=ErrorDetail(code=code, message=kind.message, fields=list(fields)))
    omitted = None if fields else {"error": {"fields"}}
    return JSONResponse(
        body.model_dump(mode="json", exclude=omitted), status_code=kind.status, headers=headers
    )


def documented_response(code: ErrorCode) -> dict[str, object]:
    response: dict[str, object] = {"model": ErrorResponse, "description": code.value}
    if code is ErrorCode.RATE_LIMITED:
        response["headers"] = {
            RETRY_AFTER_HEADER: {
                "description": "Seconds until the next request may be accepted",
                "schema": {"type": "integer", "minimum": 1},
            }
        }
    return response


def error_responses(*codes: ErrorCode) -> dict[int | str, dict[str, object]]:
    return {int(ERROR_KINDS[code].status): documented_response(code) for code in (*codes, ErrorCode.INTERNAL)}
