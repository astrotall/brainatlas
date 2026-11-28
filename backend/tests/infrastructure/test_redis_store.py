import asyncio
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

import pytest

from neuroctivity.application.errors import DependencyUnavailableError
from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.domain.review import Language, ReviewStatus, StoredReview
from neuroctivity.infrastructure.redis_scripts import Script
from neuroctivity.infrastructure.redis_store import (
    RedisKeys,
    RedisRateLimiter,
    RedisReplayGuard,
    RedisReviewStore,
    as_text,
    parse_listing,
)
from tests.fakes import T0
from tests.redis_runner import FakeRedisRunner

KEYS = RedisKeys("prod")
WINDOWS = ReviewLimits(per_hour=3, per_day=10, global_per_day=200).windows()
REVIEW = StoredReview(
    id=UUID(int=1),
    rating=5,
    text="Хороший курс.",
    lang=Language.RU,
    status=ReviewStatus.PENDING,
    created_at=T0,
)
GOOD_FIELDS = [
    "rating",
    "5",
    "text",
    "Хороший курс.",
    "lang",
    "ru",
    "status",
    "approved",
    "created_at",
    "1795862400000",
]


class CannedRunner:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.calls: list[tuple[str, list[str], list[str]]] = []

    async def run(self, script: Script, keys: Sequence[str], args: Sequence[str]) -> object:
        self.calls.append((script.name, list(keys), list(args)))
        return self.answer


def test_keys_carry_the_prefix_and_never_the_raw_token() -> None:
    key = KEYS.token("secret-token")

    assert key.startswith("prod:turnstile:")
    assert "secret-token" not in key
    assert KEYS.review(REVIEW.id) == f"prod:review:{REVIEW.id}"
    assert KEYS.index(ReviewStatus.PENDING) == "prod:reviews:pending"


def test_two_prefixes_never_share_a_key() -> None:
    assert RedisKeys("preview").review(REVIEW.id) != KEYS.review(REVIEW.id)


def test_a_new_review_is_written_as_a_hash_and_indexed_as_pending() -> None:
    runner = FakeRedisRunner()

    asyncio.run(RedisReviewStore(runner, KEYS).add_pending(REVIEW))

    stored = runner.redis.hgetall(KEYS.review(REVIEW.id))
    assert {as_text(key): as_text(value) for key, value in stored.items()} == {
        "rating": "5",
        "text": "Хороший курс.",
        "lang": "ru",
        "status": "pending",
        "created_at": "1795861800000",
    }
    assert runner.redis.zscore(KEYS.index(ReviewStatus.PENDING), str(REVIEW.id)) == 1795861800000
    assert runner.redis.zcard(KEYS.index(ReviewStatus.APPROVED)) == 0


def test_an_existing_id_is_never_overwritten() -> None:
    runner = FakeRedisRunner()
    store = RedisReviewStore(runner, KEYS)
    asyncio.run(store.add_pending(REVIEW))

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(store.add_pending(replace(REVIEW, text="Overwritten text.")))

    assert runner.redis.hget(KEYS.review(REVIEW.id), "text") == "Хороший курс.".encode()


def test_every_rate_counter_gets_a_ttl() -> None:
    runner = FakeRedisRunner()

    asyncio.run(RedisRateLimiter(runner, KEYS).acquire("client", WINDOWS, T0))

    ttls = {key.decode(): runner.redis.ttl(key) for key in runner.redis.scan_iter("prod:rl:*")}
    assert len(ttls) == 3
    assert all(0 < ttl <= 86400 for ttl in ttls.values())


def test_a_counter_left_without_a_ttl_is_given_one() -> None:
    runner = FakeRedisRunner()
    hour_key = KEYS.window(WINDOWS[0], "client", T0)
    runner.redis.set(hour_key, 1)

    asyncio.run(RedisRateLimiter(runner, KEYS).acquire("client", WINDOWS, T0))

    assert runner.redis.get(hour_key) == b"2"
    assert 0 < runner.redis.ttl(hour_key) <= 3600


def test_a_claimed_token_expires_after_its_lifetime() -> None:
    runner = FakeRedisRunner()

    asyncio.run(RedisReplayGuard(runner, KEYS, 300).claim("token"))

    assert 0 < runner.redis.ttl(KEYS.token("token")) <= 300


@pytest.mark.parametrize("answer", [None, "1", 2, -1, [0], True, b"0"])
def test_an_unexpected_claim_answer_fails_closed(answer: object) -> None:
    guard = RedisReplayGuard(CannedRunner(answer), KEYS, 300)

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(guard.claim("token"))


@pytest.mark.parametrize("answer", [None, "x", 4, -1, [1], 1.5])
def test_an_unexpected_limiter_answer_fails_closed(answer: object) -> None:
    limiter = RedisRateLimiter(CannedRunner(answer), KEYS)

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(limiter.acquire("client", WINDOWS, T0))


@pytest.mark.parametrize(("answer", "window"), [("2", 1), (b"3", 2)])
def test_a_string_limiter_answer_is_read_as_the_window_number(answer: object, window: int) -> None:
    exceeded = asyncio.run(RedisRateLimiter(CannedRunner(answer), KEYS).acquire("client", WINDOWS, T0))

    assert exceeded is WINDOWS[window]


@pytest.mark.parametrize("answer", [None, "x", 1, {"a": 1}])
def test_a_listing_that_is_not_a_list_fails_closed(answer: object) -> None:
    store = RedisReviewStore(CannedRunner(answer), KEYS)

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(store.list_approved(10))


def with_field(name: str, value: str) -> list[str]:
    fields = dict(zip(GOOD_FIELDS[::2], GOOD_FIELDS[1::2], strict=True))
    fields[name] = value
    return [item for pair in fields.items() for item in pair]


def without_field(name: str) -> list[str]:
    fields = dict(zip(GOOD_FIELDS[::2], GOOD_FIELDS[1::2], strict=True))
    del fields[name]
    return [item for pair in fields.items() for item in pair]


@pytest.mark.parametrize(
    "record",
    [
        ["not-a-uuid", GOOD_FIELDS],
        [str(UUID(int=2)), []],
        [str(UUID(int=2)), GOOD_FIELDS[:-1]],
        [str(UUID(int=2)), with_field("rating", "6")],
        [str(UUID(int=2)), with_field("rating", "five")],
        [str(UUID(int=2)), with_field("rating", chr(0x0665))],
        [str(UUID(int=2)), with_field("lang", "de")],
        [str(UUID(int=2)), with_field("status", "published")],
        [str(UUID(int=2)), with_field("text", "")],
        [str(UUID(int=2)), with_field("text", "x" * 1001)],
        [str(UUID(int=2)), with_field("created_at", "yesterday")],
        [str(UUID(int=2)), with_field("translation_en", "x" * 1001)],
        [str(UUID(int=2)), without_field("text")],
        [str(UUID(int=2)), [1, 2]],
        [str(UUID(int=2)), "flat"],
    ],
)
def test_skips_a_malformed_record_and_keeps_the_good_ones(record: list[object]) -> None:
    listed = parse_listing([str(UUID(int=1)), GOOD_FIELDS, *record])

    assert [review.id.int for review in listed] == [1]


def test_reads_bytes_from_a_redis_client_and_strings_from_the_rest_api() -> None:
    as_bytes = parse_listing([str(UUID(int=1)).encode(), [field.encode() for field in GOOD_FIELDS]])
    as_text = parse_listing([str(UUID(int=1)), GOOD_FIELDS])

    assert as_bytes == as_text


def test_an_empty_translation_slot_is_no_translation() -> None:
    [review] = parse_listing([str(UUID(int=1)), [*GOOD_FIELDS, "translation_en", ""]])

    assert review.translations == {}


@pytest.mark.parametrize("answer", [0, None, True, "1", [1]])
def test_a_create_that_is_not_confirmed_fails_closed(answer: object) -> None:
    store = RedisReviewStore(CannedRunner(answer), KEYS)

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(store.add_pending(REVIEW))
