import pytest
from fastapi.testclient import TestClient

from neuroctivity.config import Settings
from neuroctivity.main import create_app

SETTINGS_VARIABLES = ("API_DOCS_ENABLED", "VERCEL")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTINGS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings()))
