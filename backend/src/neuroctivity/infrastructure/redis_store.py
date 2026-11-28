import hashlib
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from neuroctivity.application.errors import Dependency, DependencyUnavailableError
from neuroctivity.domain.rate_limit import RateWindow, window_index, window_subject
from neuroctivity.domain.review import (
    MAX_RATING,
    MAX_TEXT_LENGTH,
    MIN_RATING,
    Language,
    ReviewStatus,
    StoredReview,
)
from neuroctivity.infrastructure.redis_scripts import (
    ACQUIRE_WINDOWS,
    CLAIM_TOKEN,
    CREATE_REVIEW,
    LIST_APPROVED,
    Script,
)

MILLISECONDS = 1000
TRANSLATION_FIELD_PREFIX = "translation_"

logger = logging.getLogger(__name__)


class ScriptRunner(Protocol):
    async def run(self, script: Script, keys: Sequence[str], args: Sequence[str]) -> object: ...


class MalformedRecordError(ValueError):
    pass


def as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, str):
        return value
    message = f"expected a string, got {type(value).__name__}"
    raise MalformedRecordError(message)


def as_int(value: object) -> int:
    if isinstance(value, bool):
        raise MalformedRecordError(type(value).__name__)
    if isinstance(value, int):
        return value
    text = as_text(value)
    if not text.isascii() or not text.lstrip("-").isdigit():
        raise MalformedRecordError(text[:16])
    return int(text)


def as_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise MalformedRecordError(type(value).__name__)
    items: list[object] = list(value)
    return items


def as_fields(value: object) -> dict[str, str]:
    flat = [as_text(item) for item in as_list(value)]
    if len(flat) % 2:
        message = "odd number of hash fields"
        raise MalformedRecordError(message)
    return dict(zip(flat[::2], flat[1::2], strict=True))


def to_milliseconds(moment: datetime) -> int:
    return round(moment.timestamp() * MILLISECONDS)


def from_milliseconds(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / MILLISECONDS, UTC)


def bounded_text(value: str) -> str:
    if not value or len(value) > MAX_TEXT_LENGTH:
        message = "text outside the stored bounds"
        raise MalformedRecordError(message)
    return value


def bounded_rating(value: str) -> int:
    rating = as_int(value)
    if not MIN_RATING <= rating <= MAX_RATING:
        raise MalformedRecordError(str(rating))
    return rating


def translations(fields: Mapping[str, str]) -> dict[Language, str]:
    return {
        lang: bounded_text(fields[name])
        for lang in Language
        if (name := f"{TRANSLATION_FIELD_PREFIX}{lang.value}") in fields and fields[name]
    }


def parse_review(review_id: str, fields: Mapping[str, str]) -> StoredReview:
    try:
        return StoredReview(
            id=UUID(review_id),
            rating=bounded_rating(fields["rating"]),
            text=bounded_text(fields["text"]),
            lang=Language(fields["lang"]),
            status=ReviewStatus(fields["status"]),
            created_at=from_milliseconds(as_int(fields["created_at"])),
            translations=translations(fields),
        )
    except (KeyError, ValueError) as error:
        raise MalformedRecordError(type(error).__name__) from error


def parse_listing(answer: object) -> list[StoredReview]:
    items = as_list(answer)
    reviews: list[StoredReview] = []
    for index in range(0, len(items) - 1, 2):
        try:
            reviews.append(parse_review(as_text(items[index]), as_fields(items[index + 1])))
        except MalformedRecordError as error:
            logger.warning("review_record_skipped", extra={"error": str(error)[:32]})
    return reviews


class RedisKeys:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def review(self, review_id: UUID | str = "") -> str:
        return f"{self._prefix}:review:{review_id}"

    def index(self, status: ReviewStatus) -> str:
        return f"{self._prefix}:reviews:{status.value}"

    def window(self, window: RateWindow, client: str, now: datetime) -> str:
        subject = window_subject(window, client)
        return f"{self._prefix}:rl:{window.name}:{subject}:{window_index(now, window.seconds)}"

    def token(self, token: str) -> str:
        return f"{self._prefix}:turnstile:{hashlib.sha256(token.encode()).hexdigest()}"


class RedisReviewStore:
    def __init__(self, runner: ScriptRunner, keys: RedisKeys) -> None:
        self._runner = runner
        self._keys = keys

    async def add_pending(self, review: StoredReview) -> None:
        keys = [self._keys.review(review.id), self._keys.index(review.status)]
        created = str(to_milliseconds(review.created_at))
        args = [
            str(review.rating),
            review.text,
            review.lang.value,
            review.status.value,
            created,
            str(review.id),
        ]
        answer = await self._runner.run(CREATE_REVIEW, keys, args)
        if type(answer) is not int or answer != 1:
            raise DependencyUnavailableError(Dependency.STORE)

    async def list_approved(self, limit: int) -> list[StoredReview]:
        keys = [self._keys.index(ReviewStatus.APPROVED)]
        answer = await self._runner.run(LIST_APPROVED, keys, [str(limit), self._keys.review()])
        try:
            return parse_listing(answer)
        except MalformedRecordError as error:
            logger.warning("review_listing_malformed", extra={"error": str(error)[:32]})
            raise DependencyUnavailableError(Dependency.STORE) from error


class RedisRateLimiter:
    def __init__(self, runner: ScriptRunner, keys: RedisKeys) -> None:
        self._runner = runner
        self._keys = keys

    async def acquire(self, client: str, windows: Sequence[RateWindow], now: datetime) -> RateWindow | None:
        keys = [self._keys.window(window, client, now) for window in windows]
        args = [str(window.limit) for window in windows] + [str(window.seconds) for window in windows]
        answer = await self._runner.run(ACQUIRE_WINDOWS, keys, args)
        try:
            exceeded = as_int(answer)
        except MalformedRecordError as error:
            raise DependencyUnavailableError(Dependency.STORE) from error
        if exceeded == 0:
            return None
        if not 1 <= exceeded <= len(windows):
            raise DependencyUnavailableError(Dependency.STORE)
        return windows[exceeded - 1]


class RedisReplayGuard:
    def __init__(self, runner: ScriptRunner, keys: RedisKeys, ttl_seconds: int) -> None:
        self._runner = runner
        self._keys = keys
        self._ttl_seconds = ttl_seconds

    async def claim(self, token: str) -> bool:
        answer = await self._runner.run(CLAIM_TOKEN, [self._keys.token(token)], [str(self._ttl_seconds)])
        if type(answer) is not int or answer not in {0, 1}:
            raise DependencyUnavailableError(Dependency.STORE)
        return answer == 1
