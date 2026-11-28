import asyncio
import logging
from dataclasses import replace
from datetime import timedelta

import pytest

from neuroctivity.application.errors import (
    Dependency,
    DependencyUnavailableError,
    HumanCheckFailedError,
    RateLimitedError,
)
from neuroctivity.domain.client import InvalidClientAddressError
from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.domain.review import Language, ReviewRuleError, ReviewStatus, ReviewSubmission, StoredReview
from neuroctivity.infrastructure.memory import MemoryReviewStore
from tests.fakes import CLIENT_ADDRESS, T0, VALID_TOKEN, Harness
from tests.logs import logged_text

SUBMISSION = ReviewSubmission(rating=5, text="A clear and careful course.", lang=Language.EN)
STRICT = ReviewLimits(per_hour=3, per_day=10, global_per_day=200)


def run_submit(harness: Harness, token: str = VALID_TOKEN, address: str = CLIENT_ADDRESS) -> None:
    asyncio.run(harness.submit()(SUBMISSION, token, address))


def test_stores_a_valid_review_as_pending_and_notifies_the_moderator() -> None:
    harness = Harness()

    run_submit(harness)

    [review] = harness.store.reviews.values()
    assert review.status is ReviewStatus.PENDING
    assert review.created_at == T0
    assert harness.notifier.calls == [(review.id, Language.EN)]


@pytest.mark.parametrize(
    "submission",
    [
        replace(SUBMISSION, rating=0),
        replace(SUBMISSION, text="too short"),
        replace(SUBMISSION, text="see example.com for more"),
    ],
)
def test_an_invalid_review_never_reaches_turnstile_or_the_store(submission: ReviewSubmission) -> None:
    harness = Harness()

    with pytest.raises(ReviewRuleError):
        asyncio.run(harness.submit()(submission, VALID_TOKEN, CLIENT_ADDRESS))

    assert harness.human_check.tokens == []
    assert harness.limiter.counters == {}
    assert harness.store.reviews == {}


def test_an_unusable_client_address_fails_before_turnstile() -> None:
    harness = Harness()

    with pytest.raises(InvalidClientAddressError):
        run_submit(harness, address="unknown")

    assert harness.human_check.tokens == []


@pytest.mark.parametrize(
    ("outcome", "error"), [("reject", HumanCheckFailedError), ("unavailable", DependencyUnavailableError)]
)
def test_a_failed_human_check_spends_no_rate_budget_and_stores_nothing(
    outcome: str, error: type[Exception]
) -> None:
    harness = Harness()
    harness.human_check.outcome = outcome

    with pytest.raises(error):
        run_submit(harness)

    assert harness.limiter.counters == {}
    assert harness.store.reviews == {}


def test_a_reused_token_is_refused_even_though_turnstile_accepted_it() -> None:
    harness = Harness()
    submit = harness.submit()

    asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))
    with pytest.raises(HumanCheckFailedError):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))

    assert len(harness.store.reviews) == 1


def test_concurrent_submissions_with_one_token_store_exactly_one_review() -> None:
    harness = Harness()
    submit = harness.submit()

    async def race() -> list[object]:
        attempts = [submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS) for _ in range(5)]
        return await asyncio.gather(*attempts, return_exceptions=True)

    outcomes = asyncio.run(race())

    assert sum(isinstance(outcome, HumanCheckFailedError) for outcome in outcomes) == 4
    assert len(harness.store.reviews) == 1


def test_the_replay_guard_can_be_switched_off_for_test_keys() -> None:
    harness = Harness(replay=False)
    submit = harness.submit()

    for _ in range(2):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))

    assert len(harness.store.reviews) == 2


def test_the_fourth_review_in_an_hour_is_rate_limited_until_the_hour_ends() -> None:
    harness = Harness(limits=STRICT, replay=False)
    submit = harness.submit()
    harness.clock.advance(timedelta(minutes=20))

    for _ in range(3):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))
    with pytest.raises(RateLimitedError) as raised:
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))

    assert raised.value.retry_after_seconds == 10 * 60
    assert len(harness.store.reviews) == 3


def test_the_hourly_budget_returns_in_the_next_hour_but_the_daily_one_does_not() -> None:
    harness = Harness(limits=ReviewLimits(per_hour=3, per_day=4, global_per_day=200), replay=False)
    submit = harness.submit()

    for _ in range(3):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))
    harness.clock.advance(timedelta(hours=1))
    asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))

    with pytest.raises(RateLimitedError):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))
    assert len(harness.store.reviews) == 4


def test_two_clients_never_share_a_bucket() -> None:
    harness = Harness(limits=ReviewLimits(per_hour=1, per_day=10, global_per_day=200), replay=False)
    submit = harness.submit()

    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.7"))
    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.8"))

    assert len(harness.store.reviews) == 2


def test_the_global_daily_cap_stops_every_client() -> None:
    harness = Harness(limits=ReviewLimits(per_hour=10, per_day=10, global_per_day=2), replay=False)
    submit = harness.submit()

    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.1"))
    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.2"))
    with pytest.raises(RateLimitedError):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.3"))


def test_a_rejected_request_does_not_drain_the_global_cap() -> None:
    harness = Harness(limits=ReviewLimits(per_hour=1, per_day=10, global_per_day=2), replay=False)
    submit = harness.submit()

    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.1"))
    for _ in range(5):
        with pytest.raises(RateLimitedError):
            asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.1"))
    asyncio.run(submit(SUBMISSION, VALID_TOKEN, "203.0.113.2"))

    assert len(harness.store.reviews) == 2


def test_concurrent_submissions_never_pass_the_limit() -> None:
    harness = Harness(limits=STRICT, replay=False)
    submit = harness.submit()

    async def race() -> list[object]:
        attempts = [submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS) for _ in range(10)]
        return await asyncio.gather(*attempts, return_exceptions=True)

    outcomes = asyncio.run(race())

    assert sum(isinstance(outcome, RateLimitedError) for outcome in outcomes) == 7
    assert len(harness.store.reviews) == 3


class FailingStore(MemoryReviewStore):
    async def add_pending(self, review: StoredReview) -> None:
        del review
        raise DependencyUnavailableError(Dependency.STORE)


def test_a_store_failure_after_the_limiter_fails_closed_and_notifies_nobody() -> None:
    harness = Harness(store=FailingStore())

    with pytest.raises(DependencyUnavailableError):
        run_submit(harness)

    assert harness.notifier.calls == []


def test_a_notifier_failure_still_accepts_the_stored_review(caplog: pytest.LogCaptureFixture) -> None:
    harness = Harness()
    harness.notifier.fail = True

    run_submit(harness)

    assert len(harness.store.reviews) == 1
    assert "moderation_notify_failed" in caplog.text


def test_never_stores_or_logs_the_address_the_token_or_the_text(caplog: pytest.LogCaptureFixture) -> None:
    harness = Harness(limits=ReviewLimits(per_hour=1, per_day=10, global_per_day=200), replay=False)
    submit = harness.submit()

    with caplog.at_level(logging.DEBUG):
        asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))
        with pytest.raises(RateLimitedError):
            asyncio.run(submit(SUBMISSION, VALID_TOKEN, CLIENT_ADDRESS))

    stored = f"{harness.store.reviews} {harness.limiter.counters}"
    logged = logged_text(caplog)
    for secret in (CLIENT_ADDRESS, VALID_TOKEN, SUBMISSION.text):
        assert secret not in logged
    assert CLIENT_ADDRESS not in stored
    assert VALID_TOKEN not in stored
