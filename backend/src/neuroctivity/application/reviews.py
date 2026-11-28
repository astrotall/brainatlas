import logging
from collections.abc import Sequence
from dataclasses import dataclass

from neuroctivity.application.errors import HumanCheckFailedError, NotificationFailedError, RateLimitedError
from neuroctivity.application.ports import (
    Clock,
    HumanCheck,
    IdFactory,
    ModerationNotifier,
    RateLimiter,
    ReplayGuard,
    ReviewStore,
)
from neuroctivity.domain.client import client_key
from neuroctivity.domain.rate_limit import ReviewLimits, seconds_until_window_end
from neuroctivity.domain.review import (
    Language,
    PublishedReview,
    ReviewSubmission,
    StoredReview,
    new_pending_review,
    publish,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SubmissionGuards:
    human_check: HumanCheck
    replay_guard: ReplayGuard | None
    rate_limiter: RateLimiter
    limits: ReviewLimits
    client_secret: bytes


@dataclass(frozen=True, slots=True)
class SubmissionEffects:
    store: ReviewStore
    notifier: ModerationNotifier
    clock: Clock
    new_id: IdFactory


class SubmitReview:
    def __init__(self, guards: SubmissionGuards, effects: SubmissionEffects) -> None:
        self._guards = guards
        self._effects = effects

    async def __call__(self, submission: ReviewSubmission, token: str, client_address: str) -> StoredReview:
        now = self._effects.clock()
        review = new_pending_review(submission, self._effects.new_id(), now)
        client = client_key(client_address, self._guards.client_secret)
        await self._verify_human(token)
        windows = self._guards.limits.windows()
        exceeded = await self._guards.rate_limiter.acquire(client, windows, now)
        if exceeded is not None:
            logger.info("review_rate_limited", extra={"window": exceeded.name})
            raise RateLimitedError(seconds_until_window_end(now, exceeded.seconds))
        await self._effects.store.add_pending(review)
        logger.info("review_submitted", extra={"review_id": str(review.id)})
        await self._notify(review)
        return review

    async def _verify_human(self, token: str) -> None:
        await self._guards.human_check.verify(token)
        guard = self._guards.replay_guard
        if guard is not None and not await guard.claim(token):
            logger.info("turnstile_token_reused")
            raise HumanCheckFailedError

    async def _notify(self, review: StoredReview) -> None:
        try:
            await self._effects.notifier.review_submitted(review.id, review.lang)
        except NotificationFailedError:
            logger.warning("moderation_notify_failed", extra={"review_id": str(review.id)})


class ListReviews:
    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    async def __call__(self, lang: Language, limit: int) -> Sequence[PublishedReview]:
        reviews = await self._store.list_approved(limit)
        published = (publish(review, lang) for review in reviews)
        return [review for review in published if review is not None]
