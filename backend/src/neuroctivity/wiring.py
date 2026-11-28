import logging
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from neuroctivity.application.ports import RateLimiter, ReplayGuard, ReviewStore
from neuroctivity.application.reviews import ListReviews, SubmissionEffects, SubmissionGuards, SubmitReview
from neuroctivity.config import ClientIpSource, Settings, StorageBackend
from neuroctivity.domain.rate_limit import ReviewLimits
from neuroctivity.infrastructure.memory import MemoryRateLimiter, MemoryReplayGuard, MemoryReviewStore
from neuroctivity.infrastructure.notifier import NoopModerationNotifier
from neuroctivity.infrastructure.redis_store import (
    RedisKeys,
    RedisRateLimiter,
    RedisReplayGuard,
    RedisReviewStore,
)
from neuroctivity.infrastructure.system import new_review_id, utc_now
from neuroctivity.infrastructure.turnstile import TEST_SECRET_KEYS, TurnstileVerifier
from neuroctivity.infrastructure.upstash import BoundedScriptRunner, upstash_evaluate
from neuroctivity.transport.reviews import ReviewEndpoints, peer_client_address, vercel_client_address

REDIS_TIMEOUT_SECONDS = 2.0
TURNSTILE_TIMEOUT_SECONDS = 3.0
TOKEN_TTL_SECONDS = 300

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Storage:
    store: ReviewStore
    rate_limiter: RateLimiter
    replay_guard: ReplayGuard


def report_missing(variables: Sequence[str]) -> None:
    logger.warning("review_configuration_missing", extra={"variables": sorted(variables)})


def missing_storage_settings(settings: Settings) -> list[str]:
    if settings.storage_backend is StorageBackend.MEMORY:
        return ["STORAGE_BACKEND=memory is not allowed on Vercel"] if settings.vercel else []
    required = {
        "UPSTASH_REDIS_REST_URL": settings.upstash_redis_rest_url,
        "UPSTASH_REDIS_REST_TOKEN": settings.upstash_redis_rest_token,
        "REDIS_KEY_PREFIX": settings.redis_key_prefix,
    }
    return [name for name, value in required.items() if value is None]


def missing_submission_settings(settings: Settings) -> list[str]:
    required = {
        "TURNSTILE_SECRET_KEY": settings.turnstile_secret_key,
        "CLIENT_HASH_SECRET": settings.client_hash_secret,
    }
    missing = [name for name, value in required.items() if value is None]
    secret = settings.turnstile_secret_key
    if settings.is_production and secret is not None and secret.get_secret_value() in TEST_SECRET_KEYS:
        missing.append("TURNSTILE_SECRET_KEY (a test key is refused in production)")
    if settings.is_production and not settings.turnstile_replay_guard:
        missing.append("TURNSTILE_REPLAY_GUARD=false is refused in production")
    return missing


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend is StorageBackend.MEMORY:
        return Storage(
            MemoryReviewStore(), MemoryRateLimiter(), MemoryReplayGuard(utc_now, TOKEN_TTL_SECONDS)
        )
    url, token, prefix = (
        settings.upstash_redis_rest_url,
        settings.upstash_redis_rest_token,
        settings.redis_key_prefix,
    )
    if url is None or token is None or prefix is None:
        raise ValueError(", ".join(missing_storage_settings(settings)))
    runner = BoundedScriptRunner(upstash_evaluate(url, token.get_secret_value()), REDIS_TIMEOUT_SECONDS)
    keys = RedisKeys(prefix)
    return Storage(
        RedisReviewStore(runner, keys),
        RedisRateLimiter(runner, keys),
        RedisReplayGuard(runner, keys, TOKEN_TTL_SECONDS),
    )


def build_submit(settings: Settings, storage: Storage) -> SubmitReview:
    secret, hash_secret = settings.turnstile_secret_key, settings.client_hash_secret
    if secret is None or hash_secret is None:
        raise ValueError(", ".join(missing_submission_settings(settings)))
    human_check = TurnstileVerifier(
        httpx.AsyncClient(timeout=TURNSTILE_TIMEOUT_SECONDS),
        secret.get_secret_value(),
        settings.turnstile_hostnames,
    )
    limits = ReviewLimits(
        per_hour=settings.review_limit_per_hour,
        per_day=settings.review_limit_per_day,
        global_per_day=settings.review_global_limit_per_day,
    )
    guards = SubmissionGuards(
        human_check=human_check,
        replay_guard=storage.replay_guard if settings.turnstile_replay_guard else None,
        rate_limiter=storage.rate_limiter,
        limits=limits,
        client_secret=hash_secret.get_secret_value().encode(),
    )
    effects = SubmissionEffects(
        store=storage.store, notifier=NoopModerationNotifier(), clock=utc_now, new_id=new_review_id
    )
    return SubmitReview(guards, effects)


def build_review_endpoints(settings: Settings) -> ReviewEndpoints:
    reader = (
        peer_client_address if settings.client_ip_source is ClientIpSource.PEER else vercel_client_address
    )
    missing_storage = missing_storage_settings(settings)
    if missing_storage:
        report_missing([*missing_storage, *missing_submission_settings(settings)])
        return ReviewEndpoints(listing=None, submit=None, read_client_address=reader)
    storage = build_storage(settings)
    missing_submission = missing_submission_settings(settings)
    if missing_submission:
        report_missing(missing_submission)
        submit = None
    else:
        submit = build_submit(settings, storage)
    return ReviewEndpoints(listing=ListReviews(storage.store), submit=submit, read_client_address=reader)
