from __future__ import annotations

import argparse
import os
from typing import Any

import uvicorn

from settings import Settings, load_settings


def merge_settings(base: Settings, overrides: dict[str, Any]) -> Settings:
    base_dict = base.model_dump() if hasattr(base, "model_dump") else {k: v for k, v in vars(base).items() if not k.startswith("_")}
    clean_overrides = {k: v for k, v in overrides.items() if v is not None}
    return Settings(**{**base_dict, **clean_overrides})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Start FastAPI app with configurable settings")
    p.add_argument("--config", "-c", help="Path to YAML config file (overrides env/.env)", default=None)
    p.add_argument("--host", help="Host to bind", default=None)
    p.add_argument("--port", type=int, help="Port to bind", default=None)
    p.add_argument("--workers", type=int, help="Number of workers (uvicorn)", default=None)
    p.add_argument("--log-level", help="Log level for uvicorn", default=None)
    p.add_argument("--reload", action="store_true", help="Enable reload (development)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.config:
        os.environ["CONFIG_FILE"] = args.config

    base = load_settings()
    overrides: dict[str, Any] = {
        "host": args.host,
        "port": args.port,
        "workers": args.workers,
        "log_level": args.log_level,
    }
    final_settings = merge_settings(base, overrides)

    uvicorn_kwargs = {
        "app": "app:app",
        "host": final_settings.host,
        "port": int(final_settings.port),
        "log_level": final_settings.log_level,
        "workers": int(final_settings.workers) if final_settings.workers and final_settings.workers > 0 else None,
        "reload": args.reload,
    }
    uvicorn_kwargs = {k: v for k, v in uvicorn_kwargs.items() if v is not None}

    print("Starting app with settings:", final_settings.model_dump() if hasattr(final_settings, "model_dump") else vars(final_settings))
    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
