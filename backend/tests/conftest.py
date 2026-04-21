from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cached_settings() -> Iterator[None]:
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("API_BASE_PATH", "/api/v1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://trading_journal:change_me@127.0.0.1:5432/trading_journal",
    )


@pytest.fixture
def client(test_env: None) -> TestClient:
    from app.main import create_app

    return TestClient(create_app())
