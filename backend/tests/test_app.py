from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

import settings
from app import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


def test_get_status(client: TestClient) -> None:
    response = client.get(f"{settings.settings.api_base}/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
