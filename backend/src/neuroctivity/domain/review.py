from enum import StrEnum

MIN_RATING = 1
MAX_RATING = 5
MIN_TEXT_LENGTH = 10
MAX_TEXT_LENGTH = 1000


class Language(StrEnum):
    RU = "ru"
    EN = "en"


class ReviewStatus(StrEnum):
    PENDING = "pending"


def normalize_review_text(text: str) -> str:
    return text.strip()
