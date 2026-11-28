import pytest

from neuroctivity.domain.review import normalize_review_text

NO_BREAK_SPACE = chr(0x00A0)
IDEOGRAPHIC_SPACE = chr(0x3000)
LINE_SEPARATOR = chr(0x2028)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("", ""),
        (" \t\r\n ", ""),
        (f"{NO_BREAK_SPACE}{IDEOGRAPHIC_SPACE}text{LINE_SEPARATOR}", "text"),
        ("  two  inner  spaces  ", "two  inner  spaces"),
        ("first line\n\nsecond line\n", "first line\n\nsecond line"),
    ],
)
def test_trims_only_the_outer_whitespace(raw: str, normalized: str) -> None:
    assert normalize_review_text(raw) == normalized
