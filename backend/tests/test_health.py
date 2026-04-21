from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_create_app_returns_fastapi_instance(test_env: None) -> None:
    from app.main import create_app

    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.state.settings.api_base_path == "/api/v1"


def test_health_endpoint_returns_ok(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_respects_configured_prefix(monkeypatch) -> None:
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://demo:demo@localhost:5432/demo")
    monkeypatch.setenv("API_BASE_PATH", "/internal")

    app = create_app()
    client = TestClient(app)

    response = client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_default_health_path_is_not_exposed_when_prefix_changes(monkeypatch) -> None:
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://demo:demo@localhost:5432/demo")
    monkeypatch.setenv("API_BASE_PATH", "/internal")

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 404
