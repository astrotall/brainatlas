from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import count
from uuid import UUID

from neuroctivity.application.errors import (
    Dependency,
    DependencyUnavailableError,
    HumanCheckFailedError,
    NotificationFailedError,
)
from neuroctivity.application.reviews import ListReviews, SubmissionEffects, SubmissionGuards, SubmitReview
from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.domain.review import Language
from neuroctivity.infrastructure.memory import MemoryRateLimiter, MemoryReplayGuard, MemoryReviewStore
from neuroctivity.transport.reviews import ReviewEndpoints, vercel_client_address

T0 = datetime(2026, 11, 28, 10, 30, tzinfo=UTC)
CLIENT_SECRET = b"s" * 32
CLIENT_ADDRESS = "203.0.113.7"
VALID_TOKEN = "valid-token"
GENEROUS = ReviewLimits(per_hour=100, per_day=100, global_per_day=100)


class Clock:
    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def sequential_ids() -> Iterator[UUID]:
    return (UUID(int=number) for number in count(1))


class IdFactory:
    def __init__(self) -> None:
        self._ids = sequential_ids()

    def __call__(self) -> UUID:
        return next(self._ids)


@dataclass
class StubHumanCheck:
    outcome: str = "pass"
    tokens: list[str] = field(default_factory=list)

    async def verify(self, token: str) -> None:
        self.tokens.append(token)
        if self.outcome == "reject":
            raise HumanCheckFailedError
        if self.outcome == "unavailable":
            raise DependencyUnavailableError(Dependency.HUMAN_CHECK)


@dataclass
class RecordingNotifier:
    fail: bool = False
    calls: list[tuple[UUID, Language]] = field(default_factory=list)

    async def review_submitted(self, review_id: UUID, lang: Language) -> None:
        self.calls.append((review_id, lang))
        if self.fail:
            raise NotificationFailedError


@dataclass
class Harness:
    store: MemoryReviewStore = field(default_factory=MemoryReviewStore)
    limiter: MemoryRateLimiter = field(default_factory=MemoryRateLimiter)
    human_check: StubHumanCheck = field(default_factory=StubHumanCheck)
    notifier: RecordingNotifier = field(default_factory=RecordingNotifier)
    clock: Clock = field(default_factory=Clock)
    limits: ReviewLimits = GENEROUS
    replay: bool = True

    def submit(self) -> SubmitReview:
        guards = SubmissionGuards(
            human_check=self.human_check,
            replay_guard=MemoryReplayGuard(self.clock, 300) if self.replay else None,
            rate_limiter=self.limiter,
            limits=self.limits,
            client_secret=CLIENT_SECRET,
        )
        effects = SubmissionEffects(
            store=self.store, notifier=self.notifier, clock=self.clock, new_id=IdFactory()
        )
        return SubmitReview(guards, effects)

    def endpoints(self) -> ReviewEndpoints:
        return ReviewEndpoints(
            listing=ListReviews(self.store), submit=self.submit(), read_client_address=vercel_client_address
        )
