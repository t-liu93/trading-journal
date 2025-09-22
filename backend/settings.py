from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    database_url: str = "sqlite:///:memory:"
    hmac_key: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


def load_settings() -> Settings:
    cfg_path = os.getenv("CONFIG_FILE")
    if cfg_path and Path(cfg_path).exists():
        with Path(cfg_path).open(encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return Settings(**data)
    return Settings()


settings = load_settings()
