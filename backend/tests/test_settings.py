from pathlib import Path

import pytest

from settings import load_settings


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    for k in ("HOST", "PORT", "WORKERS", "LOG_LEVEL"):
        monkeypatch.delenv(k, raising=False)

    s = load_settings()
    assert s.host == "0.0.0.0"  # noqa: S104
    assert s.port == 8000
    assert s.workers == 1
    assert s.log_level == "info"


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("WORKERS", "3")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.delenv("CONFIG_FILE", raising=False)

    s = load_settings()
    assert s.host == "127.0.0.1"
    assert s.port == 9000
    assert s.workers == 3
    assert s.log_level == "debug"


def test_yaml_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("host: 10.0.0.5\nport: 8088\nworkers: 5\nlog_level: debug\n")
    monkeypatch.setenv("CONFIG_FILE", str(cfg))
    for k in ("HOST", "PORT", "WORKERS", "LOG_LEVEL"):
        monkeypatch.delenv(k, raising=False)

    s = load_settings()
    assert s.host == "10.0.0.5"
    assert s.port == 8088
    assert s.workers == 5
    assert s.log_level == "debug"
