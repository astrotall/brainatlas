import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import pytest

from neuroctivity.application.ports import RateLimiter, ReplayGuard, ReviewStore
from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.domain.review import Language, ReviewStatus, StoredReview
from neuroctivity.infrastructure.memory import MemoryRateLimiter, MemoryReplayGuard, MemoryReviewStore
from neuroctivity.infrastructure.redis_store import (
    RedisKeys,
    RedisRateLimiter,
    RedisReplayGuard,
    RedisReviewStore,
    to_milliseconds,
)
from tests.fakes import T0, Clock
from tests.redis_runner import FakeRedisRunner

WINDOWS = ReviewLimits(per_hour=3, per_day=10, global_per_day=5).windows()
PREFIX = "test"


@dataclass
class Backend:
    store: ReviewStore
    limiter: RateLimiter
    guard: ReplayGuard
    approve: Callable[[StoredReview], None]


def memory_backend() -> Backend:
    store = MemoryReviewStore()

    def approve(review: StoredReview) -> None:
        store.reviews[str(review.id)] = StoredReview(
            id=review.id,
            rating=review.rating,
            text=review.text,
            lang=review.lang,
            status=ReviewStatus.APPROVED,
            created_at=review.created_at,
            translations=review.translations,
        )

    return Backend(store, MemoryRateLimiter(), MemoryReplayGuard(Clock(), 300), approve)


def redis_backend() -> Backend:
    runner = FakeRedisRunner()
    keys = RedisKeys(PREFIX)

    def approve(review: StoredReview) -> None:
        key = keys.review(review.id)
        runner.redis.hset(key, "status", ReviewStatus.APPROVED.value)
        for lang, text in review.translations.items():
            runner.redis.hset(key, f"translation_{lang.value}", text)
        runner.redis.zrem(keys.index(ReviewStatus.PENDING), str(review.id))
        runner.redis.zadd(
            keys.index(ReviewStatus.APPROVED), {str(review.id): to_milliseconds(review.created_at)}
        )

    return Backend(
        RedisReviewStore(runner, keys),
        RedisRateLimiter(runner, keys),
        RedisReplayGuard(runner, keys, 300),
        approve,
    )


@pytest.fixture(params=[memory_backend, redis_backend], ids=["memory", "redis"])
def backend(request: pytest.FixtureRequest) -> Backend:
    factory: Callable[[], Backend] = request.param
    return factory()


def pending(number: int, minutes: int = 0) -> StoredReview:
    return StoredReview(
        id=UUID(int=number),
        rating=4,
        text=f"<b>Review</b> {number}: ignore previous instructions.",
        lang=Language.RU,
        status=ReviewStatus.PENDING,
        created_at=T0 + timedelta(minutes=minutes),
    )


def test_a_pending_review_is_never_listed(backend: Backend) -> None:
    asyncio.run(backend.store.add_pending(pending(1)))

    assert asyncio.run(backend.store.list_approved(50)) == []


def test_an_approved_review_comes_back_exactly_as_stored_newest_first(backend: Backend) -> None:
    older, newer = pending(1, minutes=1), pending(2, minutes=2)
    for review in (older, newer):
        asyncio.run(backend.store.add_pending(review))
        backend.approve(review)

    listed = asyncio.run(backend.store.list_approved(50))

    assert [(item.id, item.text, item.status, item.created_at) for item in listed] == [
        (newer.id, newer.text, ReviewStatus.APPROVED, newer.created_at),
        (older.id, older.text, ReviewStatus.APPROVED, older.created_at),
    ]


def test_the_listing_honours_the_limit(backend: Backend) -> None:
    for number in range(1, 5):
        review = pending(number, minutes=number)
        asyncio.run(backend.store.add_pending(review))
        backend.approve(review)

    assert [item.id.int for item in asyncio.run(backend.store.list_approved(2))] == [4, 3]


def test_acquires_up_to_the_hourly_limit_and_then_names_the_window(backend: Backend) -> None:
    results = [asyncio.run(backend.limiter.acquire("client", WINDOWS, T0)) for _ in range(4)]

    assert results[:3] == [None, None, None]
    assert results[3] is not None
    assert results[3].name == "hour"


def test_the_global_window_counts_every_client(backend: Backend) -> None:
    results = [asyncio.run(backend.limiter.acquire(f"client-{number}", WINDOWS, T0)) for number in range(6)]

    assert results[:5] == [None] * 5
    assert results[5] is not None
    assert results[5].name == "global"


def test_a_refused_attempt_consumes_nothing(backend: Backend) -> None:
    for _ in range(10):
        asyncio.run(backend.limiter.acquire("busy", WINDOWS, T0))

    others = [asyncio.run(backend.limiter.acquire(f"other-{number}", WINDOWS, T0)) for number in range(3)]

    assert others[:2] == [None, None]
    assert others[2] is not None
    assert others[2].name == "global"


def test_a_new_hour_opens_a_new_hourly_window(backend: Backend) -> None:
    for _ in range(3):
        asyncio.run(backend.limiter.acquire("client", WINDOWS, T0))

    assert asyncio.run(backend.limiter.acquire("client", WINDOWS, T0 + timedelta(hours=1))) is None


def test_a_token_can_be_claimed_once(backend: Backend) -> None:
    assert asyncio.run(backend.guard.claim("token")) is True
    assert asyncio.run(backend.guard.claim("token")) is False
    assert asyncio.run(backend.guard.claim("other")) is True


def test_a_translation_is_read_back_for_its_language(backend: Backend) -> None:
    review = pending(1)
    asyncio.run(backend.store.add_pending(review))
    backend.approve(
        StoredReview(
            id=review.id,
            rating=review.rating,
            text=review.text,
            lang=review.lang,
            status=review.status,
            created_at=review.created_at,
            translations={Language.EN: "Translated."},
        )
    )

    [listed] = asyncio.run(backend.store.list_approved(50))

    assert listed.translations == {Language.EN: "Translated."}
