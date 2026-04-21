import pytest
from pydantic import ValidationError

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings


def test_get_settings_reads_environment(test_env: None) -> None:
    settings = get_settings()

    assert settings.app_env == "test"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 9000
    assert settings.log_level == "DEBUG"
    assert settings.api_base_path == "/api/v1"
    assert settings.database_url.endswith("/trading_journal")


def test_get_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_create_app_can_use_explicit_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(
        APP_ENV="test",
        APP_HOST="127.0.0.1",
        APP_PORT=8001,
        LOG_LEVEL="INFO",
        API_BASE_PATH="/api/v1",
        DATABASE_URL="postgresql+psycopg://demo:demo@localhost:5432/demo",
    )

    app = create_app(settings)
    client = TestClient(app)

    assert app.state.settings.database_url.endswith("/demo")
    assert client.get("/api/v1/health").status_code == 200
