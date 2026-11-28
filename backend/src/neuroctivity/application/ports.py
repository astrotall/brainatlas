from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from neuroctivity.domain.rate_limit import RateWindow
from neuroctivity.domain.review import Language, StoredReview

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


class ReviewStore(Protocol):
    async def add_pending(self, review: StoredReview) -> None: ...

    async def list_approved(self, limit: int) -> Sequence[StoredReview]: ...


class HumanCheck(Protocol):
    async def verify(self, token: str) -> None: ...


class ReplayGuard(Protocol):
    async def claim(self, token: str) -> bool: ...


class RateLimiter(Protocol):
    async def acquire(
        self, client: str, windows: Sequence[RateWindow], now: datetime
    ) -> RateWindow | None: ...


class ModerationNotifier(Protocol):
    async def review_submitted(self, review_id: UUID, lang: Language) -> None: ...
