"""Application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Field names map to env vars (case-insensitive).

    Example: `Settings.database_url` is populated from the `DATABASE_URL` env var
    (or the same key in `.env`), falling back to the default below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    cookie_secret: str = "dev-only-change-me-before-anywhere-real"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Singleton accessor. Use as a FastAPI dependency from Phase 2 onwards."""
    return Settings()
