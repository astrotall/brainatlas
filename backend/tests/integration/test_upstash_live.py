import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from upstash_redis.asyncio import Redis

from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.domain.review import Language, ReviewStatus, StoredReview
from neuroctivity.infrastructure.redis_store import (
    RedisKeys,
    RedisRateLimiter,
    RedisReplayGuard,
    RedisReviewStore,
)
from neuroctivity.infrastructure.upstash import BoundedScriptRunner, upstash_evaluate

URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (URL and TOKEN), reason="UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are not set"
    ),
]


def test_the_scripts_behave_the_same_on_real_upstash() -> None:
    prefix = f"it-{uuid4().hex[:12]}"
    keys = RedisKeys(prefix)
    runner = BoundedScriptRunner(upstash_evaluate(URL, TOKEN), timeout_seconds=5)
    review = StoredReview(
        id=uuid4(),
        rating=5,
        text="Интеграционный тест.",
        lang=Language.RU,
        status=ReviewStatus.PENDING,
        created_at=datetime.now(UTC),
    )
    windows = ReviewLimits(per_hour=1, per_day=5, global_per_day=5).windows()

    async def scenario() -> tuple[list[StoredReview], object, object, bool, bool]:
        store = RedisReviewStore(runner, keys)
        await store.add_pending(review)
        listed = await store.list_approved(10)
        limiter = RedisRateLimiter(runner, keys)
        first = await limiter.acquire("client", windows, review.created_at)
        second = await limiter.acquire("client", windows, review.created_at)
        guard = RedisReplayGuard(runner, keys, 60)
        claimed, reclaimed = await guard.claim("token"), await guard.claim("token")
        redis = Redis(url=URL, token=TOKEN, allow_telemetry=False)
        found = await redis.keys(f"{prefix}:*")
        if found:
            await redis.delete(*found)
        return listed, first, second, claimed, reclaimed

    listed, first, second, claimed, reclaimed = asyncio.run(scenario())

    assert listed == []
    assert first is None
    assert second is windows[0]
    assert (claimed, reclaimed) == (True, False)
