import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import AfterValidator, AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic_core import PydanticCustomError

from neuroctivity.application.errors import Dependency, DependencyUnavailableError
from neuroctivity.application.reviews import ListReviews, SubmitReview
from neuroctivity.domain.links import contains_link
from neuroctivity.domain.review import (
    MAX_RATING,
    MAX_TEXT_LENGTH,
    MIN_RATING,
    MIN_TEXT_LENGTH,
    Language,
    PublishedReview,
    ReviewStatus,
    ReviewSubmission,
    normalize_review_text,
)
from neuroctivity.transport.errors import ErrorCode, FieldReason, error_responses
from neuroctivity.transport.tags import Tag

REVIEWS_PATH = "/reviews"
REVIEW_ENDPOINTS_STATE = "review_endpoints"
MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = 50
MIN_TOKEN_LENGTH = 1
MAX_TOKEN_LENGTH = 2048
CANONICAL_INTEGER = re.compile(r"[1-9][0-9]{0,8}")
LIST_CACHE_CONTROL = "public, s-maxage=60, stale-while-revalidate=300"
VERCEL_FORWARDED_FOR = "x-vercel-forwarded-for"
TEXT_DESCRIPTION = (
    "Counted in Unicode code points after normalization: trimmed, NFC, control and invisible "
    "format characters removed (the emoji joiner is kept). Links are rejected."
)

router = APIRouter()

ClientAddressReader = Callable[[Request], str | None]


def vercel_client_address(request: Request) -> str | None:
    values = request.headers.getlist(VERCEL_FORWARDED_FOR)
    if not values:
        return None
    return values[-1].split(",")[-1].strip() or None


def peer_client_address(request: Request) -> str | None:
    return request.client.host if request.client else None


@dataclass(frozen=True, slots=True)
class ReviewEndpoints:
    listing: ListReviews | None
    submit: SubmitReview | None
    read_client_address: ClientAddressReader


def normalize_text_input(value: object) -> object:
    return normalize_review_text(value) if isinstance(value, str) else value


def reject_links(value: str) -> str:
    if contains_link(value):
        raise PydanticCustomError(FieldReason.LINKS_NOT_ALLOWED.value, "Links are not allowed")
    return value


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
        Field(min_length=MIN_TEXT_LENGTH, max_length=MAX_TEXT_LENGTH, description=TEXT_DESCRIPTION),
        AfterValidator(reject_links),
    ]
    lang: Annotated[
        Language, Field(description="Declared language of the text: the UI language at submit time")
    ]
    turnstile_token: Annotated[
        str, Field(alias="turnstileToken", min_length=MIN_TOKEN_LENGTH, max_length=MAX_TOKEN_LENGTH)
    ]


class ReviewAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal[ReviewStatus.PENDING]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True, validate_by_name=True)

    id: UUID
    rating: Rating
    text: str
    lang: Annotated[Language, Field(description="Language of the returned text")]
    translated: Annotated[bool, Field(description="True when the text is a translation of the original")]
    created_at: Annotated[AwareDatetime, Field(alias="createdAt")]

    @classmethod
    def of(cls, review: PublishedReview) -> "Review":
        return cls(
            id=review.id,
            rating=review.rating,
            text=review.text,
            lang=review.lang,
            translated=review.translated,
            created_at=review.created_at,
        )


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


def review_endpoints(request: Request) -> ReviewEndpoints:
    endpoints: object = getattr(request.app.state, REVIEW_ENDPOINTS_STATE, None)
    if not isinstance(endpoints, ReviewEndpoints):
        message = f"{REVIEW_ENDPOINTS_STATE} is not wired into the application state"
        raise TypeError(message)
    return endpoints


Endpoints = Annotated[ReviewEndpoints, Depends(review_endpoints)]


@router.get(
    REVIEWS_PATH,
    tags=[Tag.REVIEWS],
    dependencies=[Depends(reject_repeated_query_parameters)],
    responses=error_responses(ErrorCode.VALIDATION_FAILED, ErrorCode.SERVICE_UNAVAILABLE),
)
async def list_reviews(
    query: Annotated[ReviewListQuery, Query()], endpoints: Endpoints, response: Response
) -> ReviewList:
    if endpoints.listing is None:
        raise DependencyUnavailableError(Dependency.CONFIGURATION)
    reviews = await endpoints.listing(query.lang, query.limit)
    response.headers["Cache-Control"] = LIST_CACHE_CONTROL
    return ReviewList(items=[Review.of(review) for review in reviews])


@router.post(
    REVIEWS_PATH,
    status_code=202,
    tags=[Tag.REVIEWS],
    responses=error_responses(
        ErrorCode.TURNSTILE_FAILED,
        ErrorCode.VALIDATION_FAILED,
        ErrorCode.RATE_LIMITED,
        ErrorCode.SERVICE_UNAVAILABLE,
    ),
)
async def create_review(body: CreateReviewRequest, endpoints: Endpoints, request: Request) -> ReviewAccepted:
    if endpoints.submit is None:
        raise DependencyUnavailableError(Dependency.CONFIGURATION)
    client_address = endpoints.read_client_address(request)
    if client_address is None:
        raise DependencyUnavailableError(Dependency.CLIENT_ADDRESS)
    submission = ReviewSubmission(rating=body.rating, text=body.text, lang=body.lang)
    await endpoints.submit(submission, body.turnstile_token, client_address)
    return ReviewAccepted(status=ReviewStatus.PENDING)
