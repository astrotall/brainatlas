import re
from collections import Counter
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field

from neuroctivity.domain.review import (
    MAX_RATING,
    MAX_TEXT_LENGTH,
    MIN_RATING,
    MIN_TEXT_LENGTH,
    Language,
    ReviewStatus,
    normalize_review_text,
)
from neuroctivity.transport.errors import ErrorCode, RouteNotImplementedError, error_responses
from neuroctivity.transport.tags import Tag

REVIEWS_PATH = "/reviews"
MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 50
MIN_TOKEN_LENGTH = 1
MAX_TOKEN_LENGTH = 2048
CANONICAL_INTEGER = re.compile(r"[1-9][0-9]{0,8}")

router = APIRouter()


def normalize_text_input(value: object) -> object:
    return normalize_review_text(value) if isinstance(value, str) else value


def require_canonical_integer(value: object) -> object:
    if isinstance(value, str) and not CANONICAL_INTEGER.fullmatch(value):
        message = "expected a plain decimal integer"
        raise ValueError(message)
    return value


Rating = Annotated[int, Field(strict=True, ge=MIN_RATING, le=MAX_RATING)]


class CreateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rating: Rating
    text: Annotated[
        str,
        BeforeValidator(normalize_text_input),
        Field(
            min_length=MIN_TEXT_LENGTH,
            max_length=MAX_TEXT_LENGTH,
            description="Length is counted in Unicode code points after trimming",
        ),
    ]
    lang: Language
    turnstile_token: Annotated[
        str, Field(alias="turnstileToken", min_length=MIN_TOKEN_LENGTH, max_length=MAX_TOKEN_LENGTH)
    ]


class ReviewAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[ReviewStatus.PENDING]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    rating: Rating
    text: str
    lang: Annotated[Language, Field(description="Language of the returned text")]
    translated: Annotated[bool, Field(description="True when the text is a translation of the original")]
    created_at: Annotated[AwareDatetime, Field(alias="createdAt")]


class ReviewList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: Annotated[list[Review], Field(description="Approved reviews only, newest first")]


class ReviewListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lang: Language
    limit: Annotated[int, Field(ge=MIN_LIMIT, le=MAX_LIMIT), BeforeValidator(require_canonical_integer)] = (
        DEFAULT_LIMIT
    )


def reject_repeated_query_parameters(request: Request) -> None:
    counts = Counter(name for name, _ in request.query_params.multi_items())
    repeated = [
        {"type": "repeated_parameter", "loc": ("query", name)} for name, count in counts.items() if count > 1
    ]
    if repeated:
        raise RequestValidationError(repeated)


@router.get(
    REVIEWS_PATH,
    tags=[Tag.REVIEWS, Tag.PLANNED],
    dependencies=[Depends(reject_repeated_query_parameters)],
    responses=error_responses(
        ErrorCode.VALIDATION_FAILED, ErrorCode.NOT_IMPLEMENTED, ErrorCode.SERVICE_UNAVAILABLE
    ),
)
def list_reviews(_query: Annotated[ReviewListQuery, Query()]) -> ReviewList:
    raise RouteNotImplementedError


@router.post(
    REVIEWS_PATH,
    status_code=202,
    tags=[Tag.REVIEWS, Tag.PLANNED],
    responses=error_responses(
        ErrorCode.TURNSTILE_FAILED,
        ErrorCode.VALIDATION_FAILED,
        ErrorCode.RATE_LIMITED,
        ErrorCode.NOT_IMPLEMENTED,
        ErrorCode.SERVICE_UNAVAILABLE,
    ),
)
def create_review(_submission: CreateReviewRequest) -> ReviewAccepted:
    raise RouteNotImplementedError
