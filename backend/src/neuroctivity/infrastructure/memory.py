import hashlib
from collections.abc import Sequence
from datetime import datetime, timedelta

from neuroctivity.application.ports import Clock
from neuroctivity.domain.rate_limit import RateWindow, window_index, window_subject
from neuroctivity.domain.review import ReviewStatus, StoredReview


class MemoryReviewStore:
    def __init__(self) -> None:
        self.reviews: dict[str, StoredReview] = {}

    async def add_pending(self, review: StoredReview) -> None:
        self.reviews[str(review.id)] = review

    async def list_approved(self, limit: int) -> list[StoredReview]:
        approved = [review for review in self.reviews.values() if review.status is ReviewStatus.APPROVED]
        return sorted(approved, key=lambda review: review.created_at, reverse=True)[:limit]


class MemoryRateLimiter:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def acquire(self, client: str, windows: Sequence[RateWindow], now: datetime) -> RateWindow | None:
        keys = [
            f"{window.name}:{window_subject(window, client)}:{window_index(now, window.seconds)}"
            for window in windows
        ]
        for window, key in zip(windows, keys, strict=True):
            if self.counters.get(key, 0) >= window.limit:
                return window
        for key in keys:
            self.counters[key] = self.counters.get(key, 0) + 1
        return None


class MemoryReplayGuard:
    def __init__(self, clock: Clock, ttl_seconds: int) -> None:
        self._clock = clock
        self._ttl = timedelta(seconds=ttl_seconds)
        self.claims: dict[str, datetime] = {}

    async def claim(self, token: str) -> bool:
        now = self._clock()
        self.claims = {digest: expiry for digest, expiry in self.claims.items() if expiry > now}
        digest = hashlib.sha256(token.encode()).hexdigest()
        if digest in self.claims:
            return False
        self.claims[digest] = now + self._ttl
        return True
