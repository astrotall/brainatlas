import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from neuroctivity.domain.links import contains_link

MIN_RATING = 1
MAX_RATING = 5
MIN_TEXT_LENGTH = 10
MAX_TEXT_LENGTH = 1000

ZERO_WIDTH_JOINER = chr(0x200D)
KEPT_CONTROLS = frozenset({"\n"})
SPACE_CONTROLS = frozenset({"\t", "\v", "\f"})
LINE_BREAKS = ("\r\n", "\r", chr(0x2028), chr(0x2029), chr(0x85))
REMOVED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co"})
COMBINING_CATEGORIES = frozenset({"Mn", "Me"})
MAX_COMBINING_RUN = 4
MAX_BLANK_LINES = 1
STRAY_JOINER = re.compile(
    rf"(?<![^\s{ZERO_WIDTH_JOINER}]){ZERO_WIDTH_JOINER}|{ZERO_WIDTH_JOINER}(?![^\s{ZERO_WIDTH_JOINER}])"
)
BLANK_LINES = re.compile(rf"\n[^\S\n]*(?:\n[^\S\n]*){{{MAX_BLANK_LINES + 1},}}")


class Language(StrEnum):
    RU = "ru"
    EN = "en"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewField(StrEnum):
    RATING = "rating"
    TEXT = "text"


class RuleViolation(StrEnum):
    INVALID = "invalid"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    LINKS_NOT_ALLOWED = "links_not_allowed"


class ReviewRuleError(ValueError):
    def __init__(self, review_field: ReviewField, violation: RuleViolation) -> None:
        super().__init__(f"{review_field}: {violation}")
        self.field = review_field
        self.violation = violation


def visible_character(character: str) -> str:
    if character in KEPT_CONTROLS or character == ZERO_WIDTH_JOINER:
        return character
    if character in SPACE_CONTROLS:
        return " "
    if unicodedata.category(character) in REMOVED_CATEGORIES:
        return ""
    return character


def unify_line_breaks(text: str) -> str:
    for line_break in LINE_BREAKS:
        text = text.replace(line_break, "\n")
    return text


def limit_combining_marks(text: str) -> str:
    kept: list[str] = []
    run = 0
    for character in text:
        run = run + 1 if unicodedata.category(character) in COMBINING_CATEGORIES else 0
        if run <= MAX_COMBINING_RUN:
            kept.append(character)
    return "".join(kept)


def normalize_review_text(text: str) -> str:
    unified = unify_line_breaks(text)
    visible = "".join(visible_character(character) for character in unified)
    composed = limit_combining_marks(unicodedata.normalize("NFC", visible))
    joined = STRAY_JOINER.sub("", composed)
    return BLANK_LINES.sub("\n" * (MAX_BLANK_LINES + 1), joined).strip()


def text_violation(text: str) -> RuleViolation | None:
    if len(text) < MIN_TEXT_LENGTH:
        return RuleViolation.TOO_SHORT
    if len(text) > MAX_TEXT_LENGTH:
        return RuleViolation.TOO_LONG
    if contains_link(text):
        return RuleViolation.LINKS_NOT_ALLOWED
    return None


def validated_text(raw: str) -> str:
    text = normalize_review_text(raw)
    violation = text_violation(text)
    if violation is not None:
        raise ReviewRuleError(ReviewField.TEXT, violation)
    return text


def validated_rating(rating: object) -> int:
    if type(rating) is not int or not MIN_RATING <= rating <= MAX_RATING:
        raise ReviewRuleError(ReviewField.RATING, RuleViolation.INVALID)
    return rating


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    rating: int
    text: str
    lang: Language


@dataclass(frozen=True, slots=True)
class StoredReview:
    id: UUID
    rating: int
    text: str
    lang: Language
    status: ReviewStatus
    created_at: datetime
    translations: Mapping[Language, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PublishedReview:
    id: UUID
    rating: int
    text: str
    lang: Language
    translated: bool
    created_at: datetime


def new_pending_review(submission: ReviewSubmission, review_id: UUID, created_at: datetime) -> StoredReview:
    return StoredReview(
        id=review_id,
        rating=validated_rating(submission.rating),
        text=validated_text(submission.text),
        lang=submission.lang,
        status=ReviewStatus.PENDING,
        created_at=created_at,
    )


def publish(review: StoredReview, lang: Language) -> PublishedReview | None:
    if review.status is not ReviewStatus.APPROVED:
        return None
    translation = review.translations.get(lang) if lang is not review.lang else None
    return PublishedReview(
        id=review.id,
        rating=review.rating,
        text=translation or review.text,
        lang=lang if translation else review.lang,
        translated=bool(translation),
        created_at=review.created_at,
    )
