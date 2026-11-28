from datetime import UTC, datetime, timedelta

import pytest

from neuroctivity.domain.rate_limit import (
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    RateWindow,
    ReviewLimits,
    WindowScope,
    seconds_until_window_end,
    window_index,
    window_subject,
)

HOUR_START = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("moment", "retry_after"),
    [
        (HOUR_START, SECONDS_PER_HOUR),
        (HOUR_START + timedelta(microseconds=1), SECONDS_PER_HOUR),
        (HOUR_START + timedelta(minutes=59, seconds=59), 1),
        (HOUR_START + timedelta(minutes=59, seconds=59, microseconds=999_999), 1),
    ],
)
def test_retry_after_is_never_below_one_second_and_ends_with_the_window(
    moment: datetime, retry_after: int
) -> None:
    assert seconds_until_window_end(moment, SECONDS_PER_HOUR) == retry_after


def test_a_new_window_starts_exactly_on_the_boundary() -> None:
    last = HOUR_START - timedelta(microseconds=1)

    assert window_index(HOUR_START, SECONDS_PER_HOUR) == window_index(last, SECONDS_PER_HOUR) + 1


def test_the_day_window_follows_utc_midnight_whatever_the_offset() -> None:
    local = datetime(2026, 11, 29, 2, 0, tzinfo=UTC).astimezone()

    assert window_index(local, SECONDS_PER_DAY) == window_index(
        datetime(2026, 11, 29, tzinfo=UTC), SECONDS_PER_DAY
    )


def test_the_limits_produce_two_client_windows_and_one_global_window() -> None:
    windows = ReviewLimits(per_hour=3, per_day=10, global_per_day=200).windows()

    assert [(window.name, window.scope, window.limit, window.seconds) for window in windows] == [
        ("hour", WindowScope.CLIENT, 3, SECONDS_PER_HOUR),
        ("day", WindowScope.CLIENT, 10, SECONDS_PER_DAY),
        ("global", WindowScope.GLOBAL, 200, SECONDS_PER_DAY),
    ]


def test_the_global_window_ignores_the_client() -> None:
    window = RateWindow("global", WindowScope.GLOBAL, 1, SECONDS_PER_DAY)

    assert window_subject(window, "a") == window_subject(window, "b")
