import pytest
from fastapi.testclient import TestClient

from neuroctivity.config import Settings
from neuroctivity.main import create_app
from tests.fakes import CLIENT_ADDRESS, Harness

SETTINGS_VARIABLES = (
    "API_DOCS_ENABLED",
    "VERCEL",
    "VERCEL_ENV",
    "STORAGE_BACKEND",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "REDIS_KEY_PREFIX",
    "TURNSTILE_SECRET_KEY",
    "TURNSTILE_HOSTNAMES",
    "TURNSTILE_REPLAY_GUARD",
    "CLIENT_HASH_SECRET",
    "CLIENT_IP_SOURCE",
    "REVIEW_LIMIT_PER_HOUR",
    "REVIEW_LIMIT_PER_DAY",
    "REVIEW_GLOBAL_LIMIT_PER_DAY",
)
CLIENT_HEADERS = {"x-vercel-forwarded-for": CLIENT_ADDRESS}


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTINGS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def client(harness: Harness) -> TestClient:
    return TestClient(create_app(Settings(), harness.endpoints()), headers=CLIENT_HEADERS)
