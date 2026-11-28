import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

SECONDS_PER_HOUR = 60 * 60
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
MIN_RETRY_AFTER_SECONDS = 1


class WindowScope(StrEnum):
    CLIENT = "client"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class RateWindow:
    name: str
    scope: WindowScope
    limit: int
    seconds: int


@dataclass(frozen=True, slots=True)
class ReviewLimits:
    per_hour: int
    per_day: int
    global_per_day: int

    def windows(self) -> tuple[RateWindow, ...]:
        return (
            RateWindow("hour", WindowScope.CLIENT, self.per_hour, SECONDS_PER_HOUR),
            RateWindow("day", WindowScope.CLIENT, self.per_day, SECONDS_PER_DAY),
            RateWindow("global", WindowScope.GLOBAL, self.global_per_day, SECONDS_PER_DAY),
        )


def window_index(now: datetime, seconds: int) -> int:
    return math.floor(now.timestamp()) // seconds


def seconds_until_window_end(now: datetime, seconds: int) -> int:
    end = (window_index(now, seconds) + 1) * seconds
    return max(MIN_RETRY_AFTER_SECONDS, math.ceil(end - now.timestamp()))


def window_subject(window: RateWindow, client: str) -> str:
    return client if window.scope is WindowScope.CLIENT else WindowScope.GLOBAL.value
