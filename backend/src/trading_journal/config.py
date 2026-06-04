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
    debug: bool = False
    # NOTE: the cookie-signing secret is NOT an env var. It is generated on first
    # boot and persisted in the DB (app_config table); see auth/secret.py.
    # Production single-container only: absolute path to the built frontend
    # ``dist/`` that FastAPI serves at ``/``. Unset in dev (Vite serves the SPA
    # on :5173 and proxies ``/api``); set to ``/app/static`` inside the image.
    static_dir: str | None = None

    # Auth / session
    cookie_name: str = "trading_journal_session"
    # Secure-by-default: cookies are HTTPS-only unless explicitly relaxed. Set
    # COOKIE_SECURE=false for local plain-HTTP development.
    cookie_secure: bool = True
    session_lifetime_seconds: int = 60 * 60 * 24 * 7  # 7 days
    min_password_length: int = 8


@lru_cache
def get_settings() -> Settings:
    """Singleton accessor. Use as a FastAPI dependency from Phase 2 onwards."""
    return Settings()
