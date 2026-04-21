from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = BACKEND_DIR.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_base_path: str = Field(default="/api/v1", alias="API_BASE_PATH")
    database_url: str = Field(alias="DATABASE_URL")


@lru_cache
def get_settings() -> Settings:
    init_kwargs: dict[str, Any] = {}
    return Settings(**init_kwargs)


def clear_settings_cache() -> None:
    get_settings.cache_clear()
