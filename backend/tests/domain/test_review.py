from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from neuroctivity.domain.review import (
    Language,
    ReviewField,
    ReviewRuleError,
    ReviewStatus,
    ReviewSubmission,
    RuleViolation,
    StoredReview,
    new_pending_review,
    normalize_review_text,
    publish,
    validated_rating,
    validated_text,
)

NO_BREAK_SPACE = chr(0x00A0)
IDEOGRAPHIC_SPACE = chr(0x3000)
LINE_SEPARATOR = chr(0x2028)
ZERO_WIDTH_SPACE = chr(0x200B)
ZERO_WIDTH_JOINER = chr(0x200D)
RIGHT_TO_LEFT_OVERRIDE = chr(0x202E)
BYTE_ORDER_MARK = chr(0xFEFF)
SOFT_HYPHEN = chr(0x00AD)
LONE_SURROGATE = chr(0xD800)
PRIVATE_USE = chr(0xE000)
TAG_LETTER_A = chr(0xE0061)
COMBINING_ACUTE = chr(0x0301)
T0 = datetime(2026, 11, 28, 10, 30, tzinfo=UTC)
REVIEW_ID = UUID(int=7)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("", ""),
        (" \t\r\n ", ""),
        (f"{NO_BREAK_SPACE}{IDEOGRAPHIC_SPACE}text{LINE_SEPARATOR}", "text"),
        ("  two  inner  spaces  ", "two  inner  spaces"),
        ("first line\r\nsecond\rthird", "first line\nsecond\nthird"),
        (f"a{LINE_SEPARATOR}b", "a\nb"),
        ("tab\there", "tab here"),
        ("nul\x00bell\x07escape\x1b", "nulbellescape"),
        (f"zero{ZERO_WIDTH_SPACE}width", "zerowidth"),
        (f"{RIGHT_TO_LEFT_OVERRIDE}reversed", "reversed"),
        (f"{BYTE_ORDER_MARK}bom", "bom"),
        (f"soft{SOFT_HYPHEN}hyphen", "softhyphen"),
        (f"lone{LONE_SURROGATE}surrogate", "lonesurrogate"),
        (f"private{PRIVATE_USE}use", "privateuse"),
        (f"hidden{TAG_LETTER_A}tag", "hiddentag"),
        (f"e{COMBINING_ACUTE}", "é"),
        (f"👩{ZERO_WIDTH_JOINER}🔬", f"👩{ZERO_WIDTH_JOINER}🔬"),
        ("❤️", "❤️"),
        ("№ 10²", "№ 10²"),
        (ZERO_WIDTH_JOINER * 20, ""),
        (f"{ZERO_WIDTH_JOINER} word {ZERO_WIDTH_JOINER}", "word"),
        (f"a{ZERO_WIDTH_JOINER} b", "a b"),
        (f"👩{ZERO_WIDTH_JOINER}{ZERO_WIDTH_JOINER}🔬", "👩🔬"),
        (f"x{COMBINING_ACUTE * 50}", f"x{COMBINING_ACUTE * 4}"),
        (f"q{COMBINING_ACUTE * 5}x{COMBINING_ACUTE * 5}", f"q{COMBINING_ACUTE * 4}x{COMBINING_ACUTE * 4}"),
        ("one\n\ntwo", "one\n\ntwo"),
        ("one\n\n\n\n\ntwo", "one\n\ntwo"),
        ("one\n \n\t\n  \ntwo", "one\n\ntwo"),
    ],
)
def test_normalizes_to_visible_nfc_text(raw: str, normalized: str) -> None:
    assert normalize_review_text(raw) == normalized


def test_is_idempotent_on_its_own_output() -> None:
    once = normalize_review_text(f" {ZERO_WIDTH_SPACE}e{COMBINING_ACUTE}\r\nx{TAG_LETTER_A} ")

    assert normalize_review_text(once) == once


@pytest.mark.parametrize("rating", [1, 2, 5])
def test_accepts_an_integer_rating_from_one_to_five(rating: int) -> None:
    assert validated_rating(rating) == rating


@pytest.mark.parametrize("rating", [-1, 0, 6, True, False, "5", 5.0, None, 10**30])
def test_rejects_every_other_rating(rating: object) -> None:
    with pytest.raises(ReviewRuleError) as raised:
        validated_rating(rating)

    assert (raised.value.field, raised.value.violation) == (ReviewField.RATING, RuleViolation.INVALID)


@pytest.mark.parametrize("text", ["x" * 10, "x" * 1000, "🧠" * 1000, f"{ZERO_WIDTH_SPACE * 500}{'x' * 1000}"])
def test_accepts_text_whose_normalized_length_is_inside_the_limits(text: str) -> None:
    assert 10 <= len(validated_text(text)) <= 1000


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        ("x" * 9, RuleViolation.TOO_SHORT),
        (" " * 30, RuleViolation.TOO_SHORT),
        (ZERO_WIDTH_SPACE * 30, RuleViolation.TOO_SHORT),
        (f"{'x' * 9}{ZERO_WIDTH_SPACE}", RuleViolation.TOO_SHORT),
        ("\x00" * 12, RuleViolation.TOO_SHORT),
        (ZERO_WIDTH_JOINER * 12, RuleViolation.TOO_SHORT),
        (f"x{COMBINING_ACUTE * 999}", RuleViolation.TOO_SHORT),
        (f"ab{chr(10) * 600}cd", RuleViolation.TOO_SHORT),
        ("x" * 1001, RuleViolation.TOO_LONG),
        ("🧠" * 1001, RuleViolation.TOO_LONG),
        ("great course, see example.com", RuleViolation.LINKS_NOT_ALLOWED),
    ],
)
def test_rejects_text_that_breaks_a_rule_after_normalization(text: str, violation: RuleViolation) -> None:
    with pytest.raises(ReviewRuleError) as raised:
        validated_text(text)

    assert (raised.value.field, raised.value.violation) == (ReviewField.TEXT, violation)


def test_a_new_review_is_pending_with_the_given_id_and_time() -> None:
    review = new_pending_review(
        ReviewSubmission(rating=4, text="  A clear course.  ", lang=Language.EN), REVIEW_ID, T0
    )

    assert review == StoredReview(
        id=REVIEW_ID,
        rating=4,
        text="A clear course.",
        lang=Language.EN,
        status=ReviewStatus.PENDING,
        created_at=T0,
    )


def stored(status: ReviewStatus, translations: dict[Language, str] | None = None) -> StoredReview:
    return StoredReview(
        id=REVIEW_ID,
        rating=5,
        text="Отличный курс.",
        lang=Language.RU,
        status=status,
        created_at=T0,
        translations=translations or {},
    )


@pytest.mark.parametrize("status", [ReviewStatus.PENDING, ReviewStatus.REJECTED])
@pytest.mark.parametrize("lang", list(Language))
def test_never_publishes_a_review_that_is_not_approved(status: ReviewStatus, lang: Language) -> None:
    assert publish(stored(status, {Language.EN: "Great course."}), lang) is None


def test_publishes_the_original_in_its_own_language() -> None:
    published = publish(stored(ReviewStatus.APPROVED, {Language.EN: "Great course."}), Language.RU)

    assert published is not None
    assert (published.text, published.lang, published.translated) == ("Отличный курс.", Language.RU, False)


def test_publishes_the_translation_when_one_exists() -> None:
    published = publish(stored(ReviewStatus.APPROVED, {Language.EN: "Great course."}), Language.EN)

    assert published is not None
    assert (published.text, published.lang, published.translated) == ("Great course.", Language.EN, True)


@pytest.mark.parametrize("translations", [{}, {Language.EN: ""}])
def test_falls_back_to_the_original_when_no_translation_exists(translations: dict[Language, str]) -> None:
    published = publish(stored(ReviewStatus.APPROVED, translations), Language.EN)

    assert published is not None
    assert (published.text, published.lang, published.translated) == ("Отличный курс.", Language.RU, False)


def test_ignores_a_translation_into_the_original_language() -> None:
    review = replace(stored(ReviewStatus.APPROVED), translations={Language.RU: "Подмена."})

    published = publish(review, Language.RU)

    assert published is not None
    assert (published.text, published.translated) == ("Отличный курс.", False)
