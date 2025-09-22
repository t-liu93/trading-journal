from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app import API_BASE, app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


def test_get_status(client: TestClient) -> None:
    response = client.get(f"{API_BASE}/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
