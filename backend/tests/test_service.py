import asyncio
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY, patch

import pytest
from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import Response

from settings import settings
from trading_journal import service


# --- Auth middleware ---------------------------------------------------------
class FakeDBFactory:
    @contextmanager
    def get_session_ctx_manager(self) -> Generator[SimpleNamespace, None, None]:
        yield SimpleNamespace(name="fakesession")


def verify_json_response(response: Response, expected_status: int, expected_detail: str) -> None:
    assert response.status_code == expected_status
    body_bytes = response.body.tobytes() if isinstance(response.body, memoryview) else response.body
    body_text = body_bytes.decode("utf-8")
    body_json = json.loads(body_text)
    assert body_json.get("detail") == expected_detail


def test_auth_middleware_allows_public_path() -> None:
    app = FastAPI()
    middleware = service.AuthMiddleWare(app)

    for p in service.EXCEPT_PATHS:
        scope = {
            "type": "http",
            "method": "GET",
            "path": p,
            "headers": [],
            "client": ("testclient", 50000),
        }
        request = Request(scope)

        async def call_next(req: Request, expected: Request = request) -> Response:
            assert req is expected
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == status.HTTP_204_NO_CONTENT


def test_auth_middleware_rejects_missing_token() -> None:
    app = FastAPI()
    middleware = service.AuthMiddleWare(app)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [],
        "client": ("testclient", 50000),
    }
    request = Request(scope)

    async def call_next(req: Request) -> Response:  # noqa: ARG001
        pytest.fail("call_next should not be called for missing token")

    response = asyncio.run(middleware.dispatch(request, call_next))
    verify_json_response(response, status.HTTP_401_UNAUTHORIZED, "Unauthorized")


def test_auth_middleware_no_db() -> None:
    app = FastAPI()
    middleware = service.AuthMiddleWare(app)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"authorization", b"Bearer invalidtoken")],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request) -> Response:  # noqa: ARG001
        pytest.fail("call_next should not be called for invalid token")

    response = asyncio.run(middleware.dispatch(request, call_next))
    verify_json_response(response, status.HTTP_500_INTERNAL_SERVER_ERROR, "db factory not configured")


def test_auth_middleware_rejects_invalid_token() -> None:
    app = FastAPI()
    app.state.db_factory = FakeDBFactory()
    middleware = service.AuthMiddleWare(app)

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"authorization", b"Bearer invalidtoken")],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request) -> Response:  # noqa: ARG001
        pytest.fail("call_next should not be called for invalid token")

    with patch("trading_journal.crud.get_login_session_by_token_hash", return_value=None):
        response = asyncio.run(middleware.dispatch(request, call_next))
    verify_json_response(response, status.HTTP_401_UNAUTHORIZED, "Unauthorized")


def test_auth_middleware_rejects_expired_token() -> None:
    app = FastAPI()
    app.state.db_factory = FakeDBFactory()
    middleware = service.AuthMiddleWare(app)
    fake_token_orig = "expiredtoken"

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"cookie", f"session_token={fake_token_orig}".encode())],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request) -> Response:  # noqa: ARG001
        pytest.fail("call_next should not be called for expired token")

    expired_session = SimpleNamespace(
        id=1,
        user_id=1,
        session_token_hash="expiredtokenhash",
        created_at=None,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)),
    )

    with (
        patch("trading_journal.security.hash_session_token_sha256", return_value=expired_session.session_token_hash) as mock_hash,
        patch("trading_journal.crud.get_login_session_by_token_hash", return_value=expired_session),
        patch("trading_journal.crud.delete_login_session") as mock_delete,
    ):
        response = asyncio.run(middleware.dispatch(request, call_next))

    verify_json_response(response, status.HTTP_401_UNAUTHORIZED, "Unauthorized")
    mock_hash.assert_called_once_with(fake_token_orig)
    mock_delete.assert_called_once_with(ANY, expired_session.session_token_hash)


def test_auth_middleware_reject_inactive_user() -> None:
    app = FastAPI()
    app.state.db_factory = FakeDBFactory()
    middleware = service.AuthMiddleWare(app)
    fake_token_orig = "validtoken"

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"cookie", f"session_token={fake_token_orig}".encode())],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request) -> Response:  # noqa: ARG001
        pytest.fail("call_next should not be called for inactive user")

    inactive_user = SimpleNamespace(
        id=1,
        username="inactiveuser",
        is_active=False,
    )
    valid_session = SimpleNamespace(
        id=1,
        user_id=1,
        session_token_hash="validtokenhash",
        created_at=None,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=1)),
        user=inactive_user,
    )

    with (
        patch("trading_journal.security.hash_session_token_sha256", return_value=valid_session.session_token_hash) as mock_hash,
        patch("trading_journal.crud.get_login_session_by_token_hash", return_value=valid_session),
    ):
        response = asyncio.run(middleware.dispatch(request, call_next))

    verify_json_response(response, status.HTTP_401_UNAUTHORIZED, "Unauthorized")


# --- User services -----------------------------------------------------------
def test_register_user_success():
    pytest.fail("TODO: mock crud/security, assert UserRead username")


def test_register_user_exists_raises():
    pytest.fail("TODO: mock get_user_by_username to return obj and expect UserAlreadyExistsError")


def test_authenticate_user_success():
    pytest.fail("TODO: mock crud/security, expect token + SessionsCreate DTO")


def test_authenticate_user_invalid_password_returns_none():
    pytest.fail("TODO: mock verify_password False")


# --- Exchange services -------------------------------------------------------
def test_create_exchange_duplicate_raises():
    pytest.fail("TODO: mock get_exchange_by_name_and_user_id and expect ExchangeAlreadyExistsError")


def test_update_exchange_not_found():
    pytest.fail("TODO: mock get_exchange_by_id None and expect ExchangeNotFoundError")


# --- Cycle services ----------------------------------------------------------
def test_validate_cycle_update_rules():
    pytest.fail("TODO: call _validate_cycle_update_data with invalid combos")


def test_update_cycle_owner_mismatch_raises():
    pytest.fail("TODO: mock get_cycle_by_id owned by other user, expect CycleNotFoundError")


# --- Trade services ----------------------------------------------------------
def test_create_trade_invalid_sell_requires_expiry():
    pytest.fail("TODO: build SELL_PUT without expiry/strike, expect InvalidTradeDataError")


def test_create_trade_appends_cashflow_and_calls_crud():
    pytest.fail("TODO: mock crud.create_trade, assert net_cash_flow_cents in result")


def test_get_trade_by_id_missing_raises():
    pytest.fail("TODO: mock get_trade_by_id None, expect TradeNotFoundError")


def test_update_trade_friendly_name_not_found():
    pytest.fail("TODO: mock get_trade_by_id None, expect TradeNotFoundError")


def test_update_trade_note_sets_empty_string_when_none():
    pytest.fail("TODO: mock update_trade_note to return note '', assert DTO note")
