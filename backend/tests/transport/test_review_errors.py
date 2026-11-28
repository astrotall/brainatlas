import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from neuroctivity.application.reviews import SubmitReview
from neuroctivity.config import Settings
from neuroctivity.domain.review import (
    Language,
    ReviewField,
    ReviewRuleError,
    ReviewSubmission,
    RuleViolation,
    StoredReview,
)
from neuroctivity.infrastructure.notifier import NoopModerationNotifier
from neuroctivity.infrastructure.system import new_review_id, utc_now
from neuroctivity.main import create_app
from neuroctivity.transport import reviews
from tests.fakes import CLIENT_ADDRESS, Harness
from tests.transport.openapi import field_reasons

SUBMISSION = {"rating": 5, "text": "A clear and careful course.", "lang": "en", "turnstileToken": "t"}


class RuleBreakingSubmit(SubmitReview):
    def __init__(self, error: ReviewRuleError) -> None:
        self._error = error

    async def __call__(self, submission: ReviewSubmission, token: str, client_address: str) -> StoredReview:
        del submission, token, client_address
        raise self._error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ReviewRuleError(ReviewField.TEXT, RuleViolation.LINKS_NOT_ALLOWED), ("text", "links_not_allowed")),
        (ReviewRuleError(ReviewField.RATING, RuleViolation.INVALID), ("rating", "invalid")),
        (ReviewRuleError(ReviewField.TEXT, RuleViolation.TOO_LONG), ("text", "too_long")),
    ],
)
def test_a_domain_rule_that_fires_after_the_schema_is_still_a_422(
    error: ReviewRuleError, expected: tuple[str, str]
) -> None:
    endpoints = Harness().endpoints()
    endpoints = reviews.ReviewEndpoints(
        endpoints.listing, RuleBreakingSubmit(error), endpoints.read_client_address
    )
    client = TestClient(create_app(Settings(), endpoints), headers={"x-vercel-forwarded-for": CLIENT_ADDRESS})

    assert field_reasons(client.post("/api/reviews", json=SUBMISSION)) == [expected]


def test_an_unwired_review_endpoint_fails_loudly() -> None:
    app = FastAPI()
    app.include_router(reviews.router, prefix="/api")

    with pytest.raises(TypeError, match=reviews.REVIEW_ENDPOINTS_STATE):
        TestClient(app).get("/api/reviews?lang=ru")


def test_the_noop_notifier_accepts_every_review() -> None:
    asyncio.run(NoopModerationNotifier().review_submitted(new_review_id(), Language.RU))


def test_the_system_clock_is_utc_and_ids_are_unique() -> None:
    assert utc_now().utcoffset() is not None
    assert new_review_id() != new_review_id()
