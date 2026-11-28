from datetime import UTC, datetime
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_review_id() -> UUID:
    return uuid4()
