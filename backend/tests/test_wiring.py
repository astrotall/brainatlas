import logging

import pytest

from neuroctivity.config import Settings
from neuroctivity.wiring import build_review_endpoints, missing_storage_settings, missing_submission_settings

UPSTASH = {
    "upstash_redis_rest_url": "https://example.invalid",
    "upstash_redis_rest_token": "rest-token",
    "redis_key_prefix": "preview",
}
SUBMISSION = {"turnstile_secret_key": "real-secret", "client_hash_secret": "h" * 32}
TEST_SECRET = "1x0000000000000000000000000000000AA"


def settings(**values: object) -> Settings:
    return Settings.model_validate(values)


def test_a_complete_upstash_configuration_wires_both_endpoints() -> None:
    endpoints = build_review_endpoints(settings(**UPSTASH, **SUBMISSION))

    assert endpoints.listing is not None
    assert endpoints.submit is not None


def test_the_memory_backend_wires_both_endpoints_locally() -> None:
    endpoints = build_review_endpoints(settings(storage_backend="memory", **SUBMISSION))

    assert endpoints.listing is not None
    assert endpoints.submit is not None


@pytest.mark.parametrize("missing", sorted(UPSTASH))
def test_a_missing_storage_variable_disables_both_endpoints_and_names_it(
    missing: str, caplog: pytest.LogCaptureFixture
) -> None:
    values = {key: value for key, value in UPSTASH.items() if key != missing}

    endpoints = build_review_endpoints(settings(**values, **SUBMISSION))

    assert (endpoints.listing, endpoints.submit) == (None, None)
    record = next(
        record for record in caplog.records if record.getMessage() == "review_configuration_missing"
    )
    assert missing.upper() in str(record.__dict__["variables"])
    assert "rest-token" not in str(record.__dict__)


@pytest.mark.parametrize("missing", sorted(SUBMISSION))
def test_a_missing_submission_variable_disables_only_submission(missing: str) -> None:
    values = {key: value for key, value in SUBMISSION.items() if key != missing}

    endpoints = build_review_endpoints(settings(**UPSTASH, **values))

    assert endpoints.listing is not None
    assert endpoints.submit is None
    assert missing_submission_settings(settings(**values)) == [missing.upper()]


def test_the_memory_backend_is_refused_on_vercel() -> None:
    endpoints = build_review_endpoints(settings(storage_backend="memory", vercel="1", **SUBMISSION))

    assert (endpoints.listing, endpoints.submit) == (None, None)


@pytest.mark.parametrize(
    "values",
    [
        {"turnstile_secret_key": TEST_SECRET},
        {"turnstile_replay_guard": False},
    ],
)
def test_production_refuses_test_keys_and_a_disabled_replay_guard(values: dict[str, object]) -> None:
    production = settings(**UPSTASH, **{**SUBMISSION, **values}, vercel="1", vercel_env="production")
    preview = settings(**UPSTASH, **{**SUBMISSION, **values}, vercel="1", vercel_env="preview")

    assert build_review_endpoints(production).submit is None
    assert build_review_endpoints(preview).submit is not None


def test_nothing_is_missing_for_a_complete_configuration() -> None:
    complete = settings(**UPSTASH, **SUBMISSION)

    assert (missing_storage_settings(complete), missing_submission_settings(complete)) == ([], [])


@pytest.mark.parametrize(
    "values",
    [
        {"redis_key_prefix": "Prod"},
        {"redis_key_prefix": "a b"},
        {"redis_key_prefix": "x" * 41},
        {"client_hash_secret": "short"},
        {"review_limit_per_hour": 0},
        {"review_limit_per_day": "many"},
        {"storage_backend": "postgres"},
        {"client_ip_source": "x-forwarded-for"},
    ],
)
def test_a_malformed_value_fails_at_startup(values: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="validation error"):
        settings(**values)


def test_limits_and_hostnames_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEW_LIMIT_PER_HOUR", "5")
    monkeypatch.setenv("REVIEW_LIMIT_PER_DAY", "20")
    monkeypatch.setenv("REVIEW_GLOBAL_LIMIT_PER_DAY", "300")
    monkeypatch.setenv("TURNSTILE_HOSTNAMES", " neuroctivity.example , www.neuroctivity.example ,")

    loaded = Settings()

    assert (
        loaded.review_limit_per_hour,
        loaded.review_limit_per_day,
        loaded.review_global_limit_per_day,
    ) == (5, 20, 300)
    assert loaded.turnstile_hostnames == ["neuroctivity.example", "www.neuroctivity.example"]


def test_the_defaults_are_three_per_hour_ten_per_day_and_two_hundred_globally() -> None:
    defaults = Settings()

    assert (
        defaults.review_limit_per_hour,
        defaults.review_limit_per_day,
        defaults.review_global_limit_per_day,
    ) == (
        3,
        10,
        200,
    )
    assert defaults.turnstile_replay_guard is True


def test_secrets_never_appear_in_the_settings_repr() -> None:
    text = repr(settings(**UPSTASH, **SUBMISSION))

    assert "rest-token" not in text
    assert "real-secret" not in text


def test_a_missing_configuration_is_logged_once_at_startup(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        build_review_endpoints(Settings())

    assert [record.getMessage() for record in caplog.records].count("review_configuration_missing") == 1
