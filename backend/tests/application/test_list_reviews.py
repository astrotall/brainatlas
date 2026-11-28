import asyncio
from datetime import timedelta
from uuid import UUID

from neuroctivity.application.reviews import ListReviews
from neuroctivity.domain.review import Language, ReviewStatus, StoredReview
from neuroctivity.infrastructure.memory import MemoryReviewStore
from tests.fakes import T0


def review(number: int, status: ReviewStatus, minutes: int) -> StoredReview:
    return StoredReview(
        id=UUID(int=number),
        rating=5,
        text=f"Review number {number}.",
        lang=Language.RU,
        status=status,
        created_at=T0 + timedelta(minutes=minutes),
        translations={Language.EN: f"Translated {number}."},
    )


def store_with(*reviews: StoredReview) -> MemoryReviewStore:
    store = MemoryReviewStore()
    store.reviews = {str(item.id): item for item in reviews}
    return store


def test_lists_approved_reviews_only_newest_first_in_the_requested_language() -> None:
    store = store_with(
        review(1, ReviewStatus.APPROVED, 1),
        review(2, ReviewStatus.PENDING, 2),
        review(3, ReviewStatus.REJECTED, 3),
        review(4, ReviewStatus.APPROVED, 4),
    )

    listed = asyncio.run(ListReviews(store)(Language.EN, 50))

    assert [(item.id.int, item.text, item.translated) for item in listed] == [
        (4, "Translated 4.", True),
        (1, "Translated 1.", True),
    ]


def test_honours_the_limit() -> None:
    store = store_with(*(review(number, ReviewStatus.APPROVED, number) for number in range(1, 6)))

    listed = asyncio.run(ListReviews(store)(Language.RU, 2))

    assert [item.id.int for item in listed] == [5, 4]


class LeakyStore(MemoryReviewStore):
    async def list_approved(self, _limit: int) -> list[StoredReview]:
        return [review(1, ReviewStatus.PENDING, 1), review(2, ReviewStatus.APPROVED, 2)]


def test_drops_a_pending_review_even_if_the_store_returns_one() -> None:
    listed = asyncio.run(ListReviews(LeakyStore())(Language.RU, 50))

    assert [item.id.int for item in listed] == [2]
