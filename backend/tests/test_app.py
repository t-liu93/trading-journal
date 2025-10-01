from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import settings
import trading_journal.service as svc


@pytest.fixture
def client_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[..., TestClient]:
    class NoAuth:
        def __init__(self, app: FastAPI, **opts) -> None:  # noqa: ANN003, ARG002
            self.app = app

        async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
            state = scope.get("state")
            if state is None:
                scope["state"] = SimpleNamespace()
            scope["state"]["user_id"] = 1
            await self.app(scope, receive, send)

    class DeclineAuth:
        def __init__(self, app: FastAPI, **opts) -> None:  # noqa: ANN003, ARG002
            self.app = app

        async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
            if scope.get("type") != "http":
                await self.app(scope, receive, send)
                return
            path = scope.get("path", "")
            # allow public/exempt paths through
            if getattr(svc, "EXCEPT_PATHS", []) and path in svc.EXCEPT_PATHS:
                await self.app(scope, receive, send)
                return
            # immediately respond 401 for protected paths
            resp = JSONResponse({"detail": "Unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED)
            await resp(scope, receive, send)

    def _factory(*, decline_auth: bool = False, **mocks: dict) -> TestClient:
        defaults = {
            "register_user_service": MagicMock(return_value=SimpleNamespace(model_dump=lambda: {"id": 1, "username": "mock"})),
            "authenticate_user_service": MagicMock(
                return_value=(SimpleNamespace(user_id=1, expires_at=(datetime.now(timezone.utc) + timedelta(hours=1))), "token"),
            ),
            "create_exchange_service": MagicMock(
                return_value=SimpleNamespace(model_dump=lambda: {"name": "Binance", "notes": "some note", "user_id": 1}),
            ),
            "get_exchanges_by_user_service": MagicMock(return_value=[]),
        }

        if decline_auth:
            monkeypatch.setattr(svc, "AuthMiddleWare", DeclineAuth)
        else:
            monkeypatch.setattr(svc, "AuthMiddleWare", NoAuth)
        merged = {**defaults, **mocks}
        for name, mock in merged.items():
            monkeypatch.setattr(svc, name, mock)
        import sys

        if "app" in sys.modules:
            del sys.modules["app"]
        from importlib import import_module

        app = import_module("app").app  # re-import app module

        return TestClient(app)

    return _factory


def test_get_status(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()
    with client as c:
        response = c.get(f"{settings.settings.api_base}/status")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_register_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()  # use defaults
    with client as c:
        r = c.post(f"{settings.settings.api_base}/register", json={"username": "a", "password": "b"})
        assert r.status_code == 201


def test_register_user_already_exists(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(register_user_service=MagicMock(side_effect=svc.UserAlreadyExistsError("username already exists")))
    with client as c:
        r = c.post(f"{settings.settings.api_base}/register", json={"username": "a", "password": "b"})
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json() == {"detail": "username already exists"}


def test_register_user_internal_server_error(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(register_user_service=MagicMock(side_effect=Exception("db is down")))
    with client as c:
        r = c.post(f"{settings.settings.api_base}/register", json={"username": "a", "password": "b"})
        assert r.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert r.json() == {"detail": "Internal Server Error"}


def test_login_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()  # use defaults
    with client as c:
        r = c.post(f"{settings.settings.api_base}/login", json={"username": "a", "password": "b"})
        assert r.status_code == 200
        assert r.json() == {"user_id": 1}
        assert r.cookies.get("session_token") == "token"


def test_login_failed_auth(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(authenticate_user_service=MagicMock(return_value=None))
    with client as c:
        r = c.post(f"{settings.settings.api_base}/login", json={"username": "a", "password": "b"})
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
        assert r.json() == {"detail": "Invalid username or password, or user doesn't exist"}


def test_login_internal_server_error(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(authenticate_user_service=MagicMock(side_effect=Exception("db is down")))
    with client as c:
        r = c.post(f"{settings.settings.api_base}/login", json={"username": "a", "password": "b"})
        assert r.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert r.json() == {"detail": "Internal Server Error"}


def test_create_exchange_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()
    with client as c:
        r = c.post(f"{settings.settings.api_base}/exchanges", json={"name": "Binance"})
        assert r.status_code == 201
        assert r.json() == {"user_id": 1, "name": "Binance", "notes": "some note"}


def test_create_exchange_already_exists(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(create_exchange_service=MagicMock(side_effect=svc.ExchangeAlreadyExistsError("exchange already exists")))
    with client as c:
        r = c.post(f"{settings.settings.api_base}/exchanges", json={"name": "Binance"})
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json() == {"detail": "exchange already exists"}


def test_get_exchanges_unauthenticated(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(decline_auth=True)
    with client as c:
        r = c.get(f"{settings.settings.api_base}/exchanges")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
        assert r.json() == {"detail": "Unauthorized"}


def test_get_exchanges_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()
    with client as c:
        r = c.get(f"{settings.settings.api_base}/exchanges")
        assert r.status_code == 200
        assert r.json() == []


def test_update_exchanges_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        update_exchanges_service=MagicMock(
            return_value=SimpleNamespace(model_dump=lambda: {"user_id": 1, "name": "BinanceUS", "notes": "updated note"}),
        ),
    )
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/exchanges/1", json={"name": "BinanceUS", "notes": "updated note"})
        assert r.status_code == 200
        assert r.json() == {"user_id": 1, "name": "BinanceUS", "notes": "updated note"}


def test_update_exchanges_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(update_exchanges_service=MagicMock(side_effect=svc.ExchangeNotFoundError("exchange not found")))
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/exchanges/999", json={"name": "NonExistent", "notes": "no note"})
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "exchange not found"}


def test_get_cycles_by_id_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        get_cycle_by_id_service=MagicMock(
            return_value=SimpleNamespace(
                friendly_name="Cycle 1",
                status="active",
                id=1,
            ),
        ),
    )
    with client as c:
        r = c.get(f"{settings.settings.api_base}/cycles/1")
        assert r.status_code == 200
        assert r.json() == {"id": 1, "friendly_name": "Cycle 1", "status": "active"}


def test_get_cycles_by_id_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(get_cycle_by_id_service=MagicMock(side_effect=svc.CycleNotFoundError("cycle not found")))
    with client as c:
        r = c.get(f"{settings.settings.api_base}/cycles/999")
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "cycle not found"}


def test_get_cycles_by_user_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        get_cycles_by_user_service=MagicMock(
            return_value=[
                SimpleNamespace(
                    friendly_name="Cycle 1",
                    status="active",
                    id=1,
                ),
                SimpleNamespace(
                    friendly_name="Cycle 2",
                    status="completed",
                    id=2,
                ),
            ],
        ),
    )
    with client as c:
        r = c.get(f"{settings.settings.api_base}/cycles/user/1")
        assert r.status_code == 200
        assert r.json() == [
            {"id": 1, "friendly_name": "Cycle 1", "status": "active"},
            {"id": 2, "friendly_name": "Cycle 2", "status": "completed"},
        ]


def test_update_cycles_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        update_cycle_service=MagicMock(
            return_value=SimpleNamespace(
                friendly_name="Updated Cycle",
                status="completed",
                id=1,
            ),
        ),
    )
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/cycles", json={"friendly_name": "Updated Cycle", "status": "completed", "id": 1})
        assert r.status_code == 200
        assert r.json() == {"id": 1, "friendly_name": "Updated Cycle", "status": "completed"}


def test_update_cycles_invalid_cycle_data(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        update_cycle_service=MagicMock(side_effect=svc.InvalidCycleDataError("invalid cycle data")),
    )
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/cycles", json={"friendly_name": "", "status": "unknown", "id": 1})
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json() == {"detail": "invalid cycle data"}


def test_update_cycles_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(update_cycle_service=MagicMock(side_effect=svc.CycleNotFoundError("cycle not found")))
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/cycles", json={"friendly_name": "NonExistent", "status": "active", "id": 999})
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "cycle not found"}


def test_create_trade_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        create_trade_service=MagicMock(
            return_value=SimpleNamespace(),
        ),
    )
    with client as c:
        r = c.post(
            f"{settings.settings.api_base}/trades",
            json={
                "cycle_id": 1,
                "exchange_id": 1,
                "symbol": "BTCUSD",
                "underlying_currency": "USD",
                "trade_type": "LONG_SPOT",
                "trade_strategy": "FX",
                "quantity": 1,
                "price_cents": 15,
                "commission_cents": 100,
                "trade_date": "2025-10-01",
            },
        )
        assert r.status_code == 201


def test_create_trade_invalid_trade_data(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        create_trade_service=MagicMock(side_effect=svc.InvalidTradeDataError("invalid trade data")),
    )
    with client as c:
        r = c.post(
            f"{settings.settings.api_base}/trades",
            json={
                "cycle_id": 1,
                "exchange_id": 1,
                "symbol": "BTCUSD",
                "underlying_currency": "USD",
                "trade_type": "LONG_SPOT",
                "trade_strategy": "FX",
                "quantity": 1,
                "price_cents": 15,
                "commission_cents": 100,
                "trade_date": "2025-10-01",
            },
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert r.json() == {"detail": "invalid trade data"}


def test_get_trade_by_id_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        get_trade_by_id_service=MagicMock(
            return_value=SimpleNamespace(
                id=1,
                cycle_id=1,
                exchange_id=1,
                symbol="BTCUSD",
                underlying_currency="USD",
                trade_type="LONG_SPOT",
                trade_strategy="FX",
                quantity=1,
                price_cents=1500,
                commission_cents=100,
                trade_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
            ),
        ),
    )
    with client as c:
        r = c.get(f"{settings.settings.api_base}/trades/1")
        assert r.status_code == 200
        assert r.json() == {
            "id": 1,
            "cycle_id": 1,
            "exchange_id": 1,
            "symbol": "BTCUSD",
            "underlying_currency": "USD",
            "trade_type": "LONG_SPOT",
            "trade_strategy": "FX",
            "quantity": 1,
            "price_cents": 1500,
            "commission_cents": 100,
            "trade_date": "2025-10-01T00:00:00+00:00",
        }


def test_get_trade_by_id_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(get_trade_by_id_service=MagicMock(side_effect=svc.TradeNotFoundError("trade not found")))
    with client as c:
        r = c.get(f"{settings.settings.api_base}/trades/999")
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "trade not found"}


def test_update_trade_friendly_name_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        update_trade_friendly_name_service=MagicMock(
            return_value=SimpleNamespace(
                id=1,
                friendly_name="Updated Trade Name",
            ),
        ),
    )
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/trades/friendlyname", json={"id": 1, "friendly_name": "Updated Trade Name"})
        assert r.status_code == 200
        assert r.json() == {"id": 1, "friendly_name": "Updated Trade Name"}


def test_update_trade_friendly_name_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(update_trade_friendly_name_service=MagicMock(side_effect=svc.TradeNotFoundError("trade not found")))
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/trades/friendlyname", json={"id": 999, "friendly_name": "NonExistent Trade"})
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "trade not found"}


def test_update_trade_note_success(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(
        update_trade_note_service=MagicMock(
            return_value=SimpleNamespace(
                id=1,
                note="Updated trade note",
            ),
        ),
    )
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/trades/notes", json={"id": 1, "note": "Updated trade note"})
        assert r.status_code == 200
        assert r.json() == {"id": 1, "note": "Updated trade note"}


def test_update_trade_note_not_found(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(update_trade_note_service=MagicMock(side_effect=svc.TradeNotFoundError("trade not found")))
    with client as c:
        r = c.patch(f"{settings.settings.api_base}/trades/notes", json={"id": 999, "note": "NonExistent Trade Note"})
        assert r.status_code == status.HTTP_404_NOT_FOUND
        assert r.json() == {"detail": "trade not found"}
