import asyncio
import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import Response

from settings import settings
from trading_journal import dto, service
from trading_journal.crud import Session


# --- Auth middleware ---------------------------------------------------------
class FakeDBFactory:
    @contextmanager
    def get_session_ctx_manager(self) -> Generator[Session, None, None]:
        fake_session = MagicMock(spec=Session)
        fake_session.name = "FakeDBSession"
        yield fake_session


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
        patch("trading_journal.security.hash_session_token_sha256", return_value=valid_session.session_token_hash),
        patch("trading_journal.crud.get_login_session_by_token_hash", return_value=valid_session),
    ):
        response = asyncio.run(middleware.dispatch(request, call_next))

    verify_json_response(response, status.HTTP_401_UNAUTHORIZED, "Unauthorized")


def test_auth_middleware_allows_valid_token_and_no_update_expires() -> None:
    app = FastAPI()
    app.state.db_factory = FakeDBFactory()
    middleware = service.AuthMiddleWare(app)
    fake_token_orig = "validtoken"

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"cookie", f"session_token={fake_token_orig}".encode()), (b"user-agent", b"test-agent")],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request, expected: Request = request) -> Response:
        assert req is expected
        assert hasattr(req.state, "user_id")
        assert req.state.user_id == 1
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    active_user = SimpleNamespace(
        id=1,
        username="activeuser",
        is_active=True,
    )
    valid_session = SimpleNamespace(
        id=1,
        user_id=1,
        session_token_hash="validtokenhash",
        expires_at=(datetime.now(timezone.utc) + timedelta(days=1)),
        user=active_user,
    )

    with (
        patch("trading_journal.security.hash_session_token_sha256", return_value=valid_session.session_token_hash),
        patch("trading_journal.crud.get_login_session_by_token_hash", return_value=valid_session),
        patch("trading_journal.crud.update_login_session") as mock_update,
    ):
        response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_update.assert_called_once()
    _, kwargs = mock_update.call_args
    update_session = kwargs.get("update_session")
    assert update_session is not None
    assert update_session.expires_at == valid_session.expires_at


def test_auth_middleware_allows_valid_token_and_updates_expires() -> None:
    app = FastAPI()
    app.state.db_factory = FakeDBFactory()
    middleware = service.AuthMiddleWare(app)
    fake_token_orig = "validtoken"

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/{settings.api_base}/protected",
        "headers": [(b"cookie", f"session_token={fake_token_orig}".encode()), (b"user-agent", b"test-agent")],
        "client": ("testclient", 50000),
        "app": app,
    }
    request = Request(scope)

    async def call_next(req: Request, expected: Request = request) -> Response:
        assert req is expected
        assert hasattr(req.state, "user_id")
        assert req.state.user_id == 1
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    active_user = SimpleNamespace(
        id=1,
        username="activeuser",
        is_active=True,
    )
    valid_session = SimpleNamespace(
        id=1,
        user_id=1,
        session_token_hash="validtokenhash",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)),
        user=active_user,
    )

    with (
        patch("trading_journal.security.hash_session_token_sha256", return_value=valid_session.session_token_hash),
        patch("trading_journal.crud.get_login_session_by_token_hash", return_value=valid_session),
        patch("trading_journal.crud.update_login_session") as mock_update,
    ):
        response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_update.assert_called_once()
    _, kwargs = mock_update.call_args
    update_session = kwargs.get("update_session")
    assert update_session is not None
    assert (update_session.expires_at - datetime.now(timezone.utc)).total_seconds() > settings.session_expiry_seconds - 1
    assert (update_session.last_seen_at - datetime.now(timezone.utc)).total_seconds() < 1
    assert update_session.last_used_ip == "testclient"
    assert update_session.user_agent == "test-agent"


# --- User services -----------------------------------------------------------
def test_register_user_success() -> None:
    user_in = dto.UserCreate(username="newuser", password="newpassword")
    user_in_with_hashed_password = {
        "username": user_in.username,
        "password_hash": "hashednewpassword",
    }
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_user_by_username", return_value=None) as mock_get,
        patch(
            "trading_journal.crud.create_user",
            return_value=SimpleNamespace(id=1, username=user_in.username, is_active=True),
        ) as mock_create,
        patch("trading_journal.security.hash_password", return_value=user_in_with_hashed_password["password_hash"]),
    ):
        user_out = service.register_user_service(db, user_in)
        assert user_out.id is not None
        assert user_out.username == user_in.username
        mock_get.assert_called_once_with(db, user_in.username)
        mock_create.assert_called_once_with(db, user_data=user_in_with_hashed_password)


def test_register_user_exists_raises() -> None:
    user_in = dto.UserCreate(username="existinguser", password="newpassword")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_user_by_username",
            return_value=SimpleNamespace(id=1, username=user_in.username, is_active=True),
        ) as mock_get,
    ):
        with pytest.raises(service.UserAlreadyExistsError) as exc_info:
            service.register_user_service(db, user_in)
        assert str(exc_info.value) == "username already exists"
        mock_get.assert_called_once_with(db, user_in.username)


def test_authenticate_user_success() -> None:
    user_in = dto.UserLogin(username="validuser", password="validpassword")
    stored_user = SimpleNamespace(id=1, username=user_in.username, is_active=True, password_hash="hashedpassword")
    expected_login_session = dto.SessionsCreate(
        user_id=stored_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_expiry_seconds),
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_user_by_username",
            return_value=stored_user,
        ) as mock_get,
        patch("trading_journal.security.verify_password", return_value=True) as mock_verify,
        patch("trading_journal.security.generate_session_token", return_value="newsessiontoken") as mock_token,
        patch("trading_journal.security.hash_session_token_sha256", return_value="newsessiontokenhash") as mock_hash_session_token,
        patch(
            "trading_journal.crud.create_login_session",
            return_value=SimpleNamespace(user_id=stored_user.id, expires_at=expected_login_session.expires_at),
        ) as mock_create_session,
    ):
        user_out = service.authenticate_user_service(db, user_in)
        assert user_out is not None
        login_session, token = user_out
        # assert fields instead of direct equality to avoid pydantic/model issues
        assert getattr(login_session, "user_id", None) == stored_user.id
        assert isinstance(getattr(login_session, "expires_at", None), datetime)
        assert abs((login_session.expires_at - expected_login_session.expires_at).total_seconds()) < 2
        assert token == "newsessiontoken"
        assert login_session.user_id == stored_user.id
        mock_get.assert_called_once_with(db, user_in.username)
        mock_verify.assert_called_once_with(user_in.password, stored_user.password_hash)
        mock_token.assert_called_once()
        mock_hash_session_token.assert_called_once_with("newsessiontoken")
        mock_create_session.assert_called_once_with(
            session=db,
            user_id=stored_user.id,
            session_token_hash="newsessiontokenhash",
            session_length_seconds=settings.session_expiry_seconds,
        )


def test_authenticate_user_not_found_returns_none() -> None:
    user_in = dto.UserLogin(username="nonexistentuser", password="anypassword")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_user_by_username",
            return_value=None,
        ) as mock_get,
    ):
        user_out = service.authenticate_user_service(db, user_in)
        assert user_out is None
        mock_get.assert_called_once_with(db, user_in.username)


def test_authenticate_user_invalid_password_returns_none() -> None:
    user_in = dto.UserLogin(username="validuser", password="invalidpassword")
    stored_user = SimpleNamespace(id=1, username=user_in.username, is_active=True, password_hash="hashedpassword")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_user_by_username",
            return_value=stored_user,
        ) as mock_get,
        patch("trading_journal.security.verify_password", return_value=False) as mock_verify,
    ):
        user_out = service.authenticate_user_service(db, user_in)
        assert user_out is None
        mock_get.assert_called_once_with(db, user_in.username)
        mock_verify.assert_called_once_with(user_in.password, stored_user.password_hash)


# --- Exchange services -------------------------------------------------------
def test_create_exchange_duplicate_raises() -> None:
    exchange_in = dto.ExchangesCreate(user_id=1, name="NYSE", notes="Test exchange")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_name_and_user_id",
            return_value=SimpleNamespace(id=1, user_id=1, name=exchange_in.name, notes="Existing exchange"),
        ) as mock_get,
    ):
        with pytest.raises(service.ExchangeAlreadyExistsError) as exc_info:
            service.create_exchange_service(db, user_id=exchange_in.user_id, name=exchange_in.name, notes=exchange_in.notes)
        assert str(exc_info.value) == "Exchange with the same name already exists for this user"
        mock_get.assert_called_once_with(db, exchange_in.name, exchange_in.user_id)


def test_create_exchange_success() -> None:
    exchange_in = dto.ExchangesCreate(user_id=1, name="NASDAQ", notes="New exchange")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_name_and_user_id",
            return_value=None,
        ) as mock_get,
        patch(
            "trading_journal.crud.create_exchange",
            return_value=SimpleNamespace(id=2, user_id=exchange_in.user_id, name=exchange_in.name, notes=exchange_in.notes),
        ) as mock_create,
    ):
        exchange_out = service.create_exchange_service(db, user_id=exchange_in.user_id, name=exchange_in.name, notes=exchange_in.notes)
        assert exchange_out.name == exchange_in.name
        assert exchange_out.notes == exchange_in.notes
        mock_get.assert_called_once_with(db, exchange_in.name, exchange_in.user_id)
        mock_create.assert_called_once_with(db, exchange_data=exchange_in)


def test_get_exchanges_by_user_id() -> None:
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_all_exchanges_by_user_id",
            return_value=[
                SimpleNamespace(id=1, user_id=1, name="NYSE", notes="First exchange"),
                SimpleNamespace(id=2, user_id=1, name="NASDAQ", notes="Second exchange"),
            ],
        ) as mock_get,
    ):
        exchanges = service.get_exchanges_by_user_service(db, user_id=1)
        assert len(exchanges) == 2
        assert exchanges[0].name == "NYSE"
        assert exchanges[1].name == "NASDAQ"
        mock_get.assert_called_once_with(db, 1)


def test_get_exchanges_by_user_no_exchanges() -> None:
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_all_exchanges_by_user_id",
            return_value=[],
        ) as mock_get,
    ):
        exchanges = service.get_exchanges_by_user_service(db, user_id=1)
        assert len(exchanges) == 0
        mock_get.assert_called_once_with(db, 1)


def test_update_exchange_not_found() -> None:
    exchange_update = dto.ExchangesBase(name="UpdatedName", notes="Updated notes")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_id",
            return_value=None,
        ) as mock_get,
    ):
        with pytest.raises(service.ExchangeNotFoundError) as exc_info:
            service.update_exchanges_service(db, exchange_id=1, user_id=1, name=exchange_update.name, notes=exchange_update.notes)
        assert str(exc_info.value) == "Exchange not found"
        mock_get.assert_called_once_with(db, 1)


def test_update_exchange_owner_mismatch_raises() -> None:
    exchange_update = dto.ExchangesBase(name="UpdatedName", notes="Updated notes")
    existing_exchange = SimpleNamespace(id=1, user_id=2, name="OldName", notes="Old notes")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_id",
            return_value=existing_exchange,
        ) as mock_get,
    ):
        with pytest.raises(service.ExchangeNotFoundError) as exc_info:
            service.update_exchanges_service(db, exchange_id=1, user_id=1, name=exchange_update.name, notes=exchange_update.notes)
        assert str(exc_info.value) == "Exchange not found"
        mock_get.assert_called_once_with(db, 1)


def test_update_exchange_duplication() -> None:
    exchange_update = dto.ExchangesBase(name="DuplicateName", notes="Updated notes")
    existing_exchange = SimpleNamespace(id=1, user_id=1, name="OldName", notes="Old notes")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_id",
            return_value=existing_exchange,
        ) as mock_get,
        patch(
            "trading_journal.crud.get_exchange_by_name_and_user_id",
            return_value=SimpleNamespace(id=2, user_id=1, name="DuplicateName", notes="Another exchange"),
        ) as mock_get_by_name,
    ):
        with pytest.raises(service.ExchangeAlreadyExistsError) as exc_info:
            service.update_exchanges_service(db, exchange_id=1, user_id=1, name=exchange_update.name, notes=exchange_update.notes)
        assert str(exc_info.value) == "Another exchange with the same name already exists for this user"
        mock_get.assert_called_once_with(db, 1)
        mock_get_by_name.assert_called_once_with(db, "DuplicateName", 1)


def test_update_exchange_success() -> None:
    exchange_update = dto.ExchangesBase(name="UpdatedName", notes="Updated notes")
    existing_exchange = SimpleNamespace(id=1, user_id=1, name="OldName", notes="Old notes")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch(
            "trading_journal.crud.get_exchange_by_id",
            return_value=existing_exchange,
        ) as mock_get,
        patch(
            "trading_journal.crud.get_exchange_by_name_and_user_id",
            return_value=None,
        ) as mock_get_by_name,
        patch(
            "trading_journal.crud.update_exchange",
            return_value=SimpleNamespace(id=1, user_id=1, name=exchange_update.name, notes=exchange_update.notes),
        ) as mock_update,
    ):
        exchange_out = service.update_exchanges_service(db, exchange_id=1, user_id=1, name=exchange_update.name, notes=exchange_update.notes)
        assert exchange_out.name == exchange_update.name
        assert exchange_out.notes == exchange_update.notes
        mock_get.assert_called_once_with(db, 1)
        mock_get_by_name.assert_called_once_with(db, "UpdatedName", 1)
        mock_update.assert_called_once_with(db, 1, update_data=exchange_update)


# --- Cycle services ----------------------------------------------------------
def test_get_cycle_by_id_not_found_raises() -> None:
    user_id = 1
    cycle_id = 1
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=None) as mock_get,
    ):
        with pytest.raises(service.CycleNotFoundError) as exc_info:
            service.get_cycle_by_id_service(db, user_id=user_id, cycle_id=cycle_id)
        assert str(exc_info.value) == "Cycle not found"
        mock_get.assert_called_once_with(db, cycle_id)


def test_get_cycle_by_id_owner_mismatch_raises() -> None:
    user_id = 1
    cycle_id = 1
    cycle = SimpleNamespace(id=cycle_id, user_id=2)  # Owned by different user
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=cycle) as mock_get,
    ):
        with pytest.raises(service.CycleNotFoundError) as exc_info:
            service.get_cycle_by_id_service(db, user_id=user_id, cycle_id=cycle_id)
        assert str(exc_info.value) == "Cycle not found"
        mock_get.assert_called_once_with(db, cycle_id)


def test_get_cycle_by_id_success() -> None:
    user_id = 1
    cycle_id = 1
    cycle = SimpleNamespace(
        id=cycle_id,
        friendly_name="Test Cycle",
        status="OPEN",
        funding_source="MIXED",
        user_id=user_id,
        symbol="AAPL",
        exchange_id=1,
        underlying_currency="USD",
        start_date=datetime.now(timezone.utc).date(),
        trades=[],
        exchange=None,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=cycle) as mock_get,
    ):
        cycle_out = service.get_cycle_by_id_service(db, user_id=user_id, cycle_id=cycle_id)
        assert cycle_out.id == cycle_id
        assert cycle_out.user_id == user_id
        assert cycle_out.friendly_name == "Test Cycle"
        assert cycle_out.status == "OPEN"
        assert cycle_out.funding_source == "MIXED"
        assert cycle_out.symbol == "AAPL"
        assert cycle_out.exchange_id == 1
        assert cycle_out.underlying_currency == "USD"
        assert cycle_out.trades == []
        mock_get.assert_called_once_with(db, cycle_id)


def test_get_cycles_by_user_no_cycles() -> None:
    user_id = 1
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycles_by_user_id", return_value=[]) as mock_get,
    ):
        cycles = service.get_cycles_by_user_service(db, user_id=user_id)
        assert isinstance(cycles, list)
        assert len(cycles) == 0
        mock_get.assert_called_once_with(db, user_id)


def test_get_cycles_by_user_with_cycles() -> None:
    user_id = 1
    cycle1 = SimpleNamespace(
        id=1,
        friendly_name="Cycle 1",
        status="OPEN",
        funding_source="MIXED",
        user_id=user_id,
        symbol="AAPL",
        exchange_id=1,
        underlying_currency="USD",
        start_date=datetime.now(timezone.utc).date(),
        trades=[],
        exchange=None,
    )
    cycle2 = SimpleNamespace(
        id=2,
        friendly_name="Cycle 2",
        status="CLOSED",
        funding_source="LOAN",
        user_id=user_id,
        symbol="TSLA",
        exchange_id=2,
        underlying_currency="USD",
        start_date=datetime.now(timezone.utc).date() - timedelta(days=30),
        trades=[],
        exchange=None,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycles_by_user_id", return_value=[cycle1, cycle2]) as mock_get,
    ):
        cycles = service.get_cycles_by_user_service(db, user_id=user_id)
        assert isinstance(cycles, list)
        assert len(cycles) == 2
        assert cycles[0].id == 1
        assert cycles[0].friendly_name == "Cycle 1"
        assert cycles[1].id == 2
        assert cycles[1].friendly_name == "Cycle 2"
        mock_get.assert_called_once_with(db, user_id)


def test_update_cycle_closed_status_mismatch_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="CLOSED")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "end_date is required when status is CLOSED"


def test_update_cycle_open_status_mismatch_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN", end_date=datetime.now(timezone.utc).date())
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "end_date must be empty when status is OPEN"


def test_update_cycle_invalid_capital_exposure_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN", capital_exposure_cents=-100)
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "capital_exposure_cents must be non-negative"


def test_update_cycle_no_cash_no_loan_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN", funding_source="LOAN", loan_amount_cents=None)
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "loan_amount_cents and loan_interest_rate_tenth_bps are required when funding_source is not CASH"


def test_update_cycle_loan_missing_interest_raises() -> None:
    cycle_data = dto.CycleUpdate(
        id=1,
        friendly_name="Updated Cycle",
        status="OPEN",
        funding_source="LOAN",
        loan_amount_cents=10000,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "loan_amount_cents and loan_interest_rate_tenth_bps are required when funding_source is not CASH"


def test_update_cycle_loan_negative_loan_raises() -> None:
    cycle_data = dto.CycleUpdate(
        id=1,
        friendly_name="Updated Cycle",
        status="OPEN",
        funding_source="LOAN",
        loan_amount_cents=-10000,
        loan_interest_rate_tenth_bps=50,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "loan_amount_cents must be non-negative"


def test_update_cycle_loan_negative_interest_raises() -> None:
    cycle_data = dto.CycleUpdate(
        id=1,
        friendly_name="Updated Cycle",
        status="OPEN",
        funding_source="LOAN",
        loan_amount_cents=10000,
        loan_interest_rate_tenth_bps=-50,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidCycleDataError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "loan_interest_rate_tenth_bps must be non-negative"


def test_update_cycle_not_found_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN")
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=None) as mock_get,
    ):
        with pytest.raises(service.CycleNotFoundError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "Cycle not found"
        mock_get.assert_called_once_with(db, cycle_data.id)


def test_update_cycle_owner_mismatch_raises() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN")
    existing_cycle = SimpleNamespace(id=1, user_id=2)  # Owned by different user
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=existing_cycle) as mock_get,
    ):
        with pytest.raises(service.CycleNotFoundError) as exc_info:
            service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert str(exc_info.value) == "Cycle not found"
        mock_get.assert_called_once_with(db, cycle_data.id)


def test_update_cycle_success() -> None:
    cycle_data = dto.CycleUpdate(id=1, friendly_name="Updated Cycle", status="OPEN", funding_source="CASH", capital_exposure_cents=5000)
    existing_cycle = SimpleNamespace(
        id=1,
        user_id=1,
        friendly_name="Old Cycle",
        symbol="AAPL",
        exchange_id=1,
        underlying_currency="USD",
        start_date=datetime.now(timezone.utc).date(),
        status="OPEN",
        funding_source="MIXED",
        capital_exposure_cents=10000,
        loan_amount_cents=2000,
        loan_interest_rate_tenth_bps=50,
    )
    updated_cycle = SimpleNamespace(
        id=1,
        user_id=1,
        symbol="AAPL",
        exchange_id=1,
        underlying_currency="USD",
        start_date=existing_cycle.start_date,
        friendly_name="Updated Cycle",
        status=cycle_data.status,
        funding_source=cycle_data.funding_source,
        capital_exposure_cents=cycle_data.capital_exposure_cents,
        loan_amount_cents=None,
        loan_interest_rate_tenth_bps=None,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_cycle_by_id", return_value=existing_cycle) as mock_get,
        patch("trading_journal.crud.update_cycle", return_value=updated_cycle) as mock_update,
    ):
        cycle_out = service.update_cycle_service(db, user_id=1, cycle_data=cycle_data)
        assert cycle_out.id == updated_cycle.id
        assert cycle_out.friendly_name == updated_cycle.friendly_name
        assert cycle_out.status == updated_cycle.status
        assert cycle_out.funding_source == updated_cycle.funding_source
        assert cycle_out.capital_exposure_cents == updated_cycle.capital_exposure_cents
        assert cycle_out.loan_amount_cents is None
        assert cycle_out.loan_interest_rate_tenth_bps is None
        mock_get.assert_called_once_with(db, cycle_data.id)
        update_cycle_base = dto.CycleBase(
            friendly_name=cycle_data.friendly_name,
            status=cycle_data.status,
            funding_source=cycle_data.funding_source,
            capital_exposure_cents=cycle_data.capital_exposure_cents,
            loan_amount_cents=getattr(cycle_data, "loan_amount_cents", None),
            loan_interest_rate_tenth_bps=getattr(cycle_data, "loan_interest_rate_tenth_bps", None),
            end_date=getattr(cycle_data, "end_date", None),
        )
        mock_update.assert_called_once_with(db, cycle_data.id, update_data=update_cycle_base)


# --- Trade services ----------------------------------------------------------
def test_create_trade_short_option_no_strike() -> None:
    trade_data = dto.TradeCreate(
        user_id=1,
        symbol="AAPL",
        exchange_id=1,
        underlying_currency=dto.UnderlyingCurrency.USD,
        trade_type=dto.TradeType.SELL_PUT,
        trade_strategy=dto.TradeStrategy.WHEEL,
        trade_date=datetime.now(timezone.utc).date(),
        quantity=-1,
        price_cents=5000,
        commission_cents=100,
        cycle_id=1,
        friendly_name="Short Call",
        notes="Test trade",
        quantity_multiplier=100,
        expiry_date=datetime.now(timezone.utc).date() + timedelta(days=30),
        strike_price_cents=None,  # Missing strike price
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
    ):
        with pytest.raises(service.InvalidTradeDataError) as exc_info:
            service.create_trade_service(db, 1, trade_data)
        assert str(exc_info.value) == "Invalid trade data: expiry_date and strike_price_cents are required for SELL_PUT and SELL_CALL trades"


def test_create_trade_success() -> None:
    trade_data = dto.TradeCreate(
        user_id=1,
        symbol="AAPL",
        exchange_id=1,
        underlying_currency=dto.UnderlyingCurrency.USD,
        trade_type=dto.TradeType.SELL_PUT,
        trade_strategy=dto.TradeStrategy.WHEEL,
        trade_date=datetime.now(timezone.utc).date(),
        strike_price_cents=15000,
        expiry_date=datetime.now(timezone.utc).date() + timedelta(days=30),
        quantity=1,
        price_cents=5000,
        commission_cents=100,
        cycle_id=1,
        friendly_name="Sell put",
        notes="Test trade",
        quantity_multiplier=1,
    )
    created_trade = SimpleNamespace(
        id=1,
        user_id=trade_data.user_id,
        symbol=trade_data.symbol,
        exchange_id=trade_data.exchange_id,
        underlying_currency=trade_data.underlying_currency,
        trade_type=trade_data.trade_type,
        trade_strategy=trade_data.trade_strategy,
        trade_date=trade_data.trade_date,
        quantity=trade_data.quantity,
        price_cents=trade_data.price_cents,
        commission_cents=trade_data.commission_cents,
        cycle_id=trade_data.cycle_id,
        friendly_name=trade_data.friendly_name,
        notes=trade_data.notes,
        quantity_multiplier=trade_data.quantity_multiplier,
        expiry_date=trade_data.expiry_date,
        strike_price_cents=trade_data.strike_price_cents,
    )
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.create_trade", return_value=created_trade) as mock_create_trade,
    ):
        trade_out = service.create_trade_service(db, user_id=1, trade_data=trade_data)
        assert trade_out.id == created_trade.id
        assert trade_out.user_id == created_trade.user_id
        assert trade_out.symbol == created_trade.symbol
        assert trade_out.trade_type == created_trade.trade_type
        mock_create_trade.assert_called_once()
        _, kwargs = mock_create_trade.call_args
        passed_trade = kwargs.get("trade_data") or (mock_create_trade.call_args[0][1] if len(mock_create_trade.call_args[0]) > 1 else None)
        assert passed_trade is not None
        # expected for SELL_PUT: gross = quantity * price * quantity_multiplier (positive), net = gross - commission
        expected_gross = trade_data.quantity * trade_data.price_cents * (trade_data.quantity_multiplier or 1)
        expected_net = expected_gross - trade_data.commission_cents
        assert getattr(passed_trade, "gross_cash_flow_cents", None) == expected_gross
        assert getattr(passed_trade, "net_cash_flow_cents", None) == expected_net


def test_get_trade_by_id_not_found_when_missing() -> None:
    with FakeDBFactory().get_session_ctx_manager() as db, patch("trading_journal.crud.get_trade_by_id", return_value=None) as mock_get:
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.get_trade_by_id_service(db, user_id=1, trade_id=1)
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 1)


def test_get_trade_by_id_not_found_owner_mismatch() -> None:
    existing_trade = SimpleNamespace(id=2, user_id=2)
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_trade_by_id", return_value=existing_trade) as mock_get,
    ):
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.get_trade_by_id_service(db, user_id=1, trade_id=2)
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 2)


def test_get_trade_by_id_success() -> None:
    # build a trade-like object compatible with dto.TradeRead/model_validate
    trade_obj = SimpleNamespace(
        id=10,
        user_id=1,
        friendly_name="Test Trade",
        symbol="AAPL",
        exchange_id=1,
        underlying_currency=dto.UnderlyingCurrency.USD,
        trade_type=dto.TradeType.LONG_SPOT,
        trade_strategy=dto.TradeStrategy.SPOT,
        trade_date=datetime.now(timezone.utc).date(),
        trade_time_utc=None,
        expiry_date=None,
        strike_price_cents=None,
        quantity=1,
        quantity_multiplier=1,
        price_cents=1000,
        gross_cash_flow_cents=-1000,
        commission_cents=10,
        net_cash_flow_cents=-1010,
        is_invalidated=False,
        invalidated_at=None,
        replaced_by_trade_id=None,
        notes="ok",
        cycle_id=None,
    )
    with FakeDBFactory().get_session_ctx_manager() as db, patch("trading_journal.crud.get_trade_by_id", return_value=trade_obj) as mock_get:
        res = service.get_trade_by_id_service(db, user_id=1, trade_id=10)
        assert res.id == trade_obj.id
        assert res.user_id == trade_obj.user_id
        assert res.symbol == trade_obj.symbol
        assert res.trade_type == trade_obj.trade_type
        mock_get.assert_called_once_with(db, 10)


def test_update_trade_friendly_name_not_found() -> None:
    with FakeDBFactory().get_session_ctx_manager() as db, patch("trading_journal.crud.get_trade_by_id", return_value=None) as mock_get:
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.update_trade_friendly_name_service(db, user_id=1, trade_id=10, friendly_name="New Name")
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 10)


def test_update_trade_friendly_name_owner_mismatch_raises() -> None:
    existing_trade = SimpleNamespace(id=10, user_id=2)  # owned by another user
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_trade_by_id", return_value=existing_trade) as mock_get,
    ):
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.update_trade_friendly_name_service(db, user_id=1, trade_id=10, friendly_name="New Name")
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 10)


def test_update_trade_friendly_name_success() -> None:
    existing_trade = SimpleNamespace(
        id=10,
        user_id=1,
        friendly_name="Old Name",
        symbol="AAPL",
        exchange_id=1,
        underlying_currency=dto.UnderlyingCurrency.USD,
        trade_type=dto.TradeType.LONG_SPOT,
        trade_strategy=dto.TradeStrategy.SPOT,
        trade_date=datetime.now(timezone.utc).date(),
        trade_time_utc=None,
        expiry_date=None,
        strike_price_cents=None,
        quantity=1,
        quantity_multiplier=1,
        price_cents=1000,
        gross_cash_flow_cents=-1000,
        commission_cents=10,
        net_cash_flow_cents=-1010,
        is_invalidated=False,
        invalidated_at=None,
        replaced_by_trade_id=None,
        notes="ok",
        cycle_id=None,
    )
    updated_trade = SimpleNamespace(**{**existing_trade.__dict__, "friendly_name": "New Friendly"})
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_trade_by_id", return_value=existing_trade) as mock_get,
        patch("trading_journal.crud.update_trade_friendly_name", return_value=updated_trade) as mock_update,
    ):
        res = service.update_trade_friendly_name_service(db, user_id=1, trade_id=10, friendly_name="New Friendly")
        assert res.friendly_name == "New Friendly"
        mock_get.assert_called_once_with(db, 10)
        mock_update.assert_called_once_with(db, 10, "New Friendly")


def test_update_trade_note_not_found() -> None:
    with FakeDBFactory().get_session_ctx_manager() as db, patch("trading_journal.crud.get_trade_by_id", return_value=None) as mock_get:
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.update_trade_note_service(db, user_id=1, trade_id=20, note="x")
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 20)


def test_update_trade_note_owner_mismatch_raises() -> None:
    existing_trade = SimpleNamespace(id=20, user_id=2)
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_trade_by_id", return_value=existing_trade) as mock_get,
    ):
        with pytest.raises(service.TradeNotFoundError) as exc_info:
            service.update_trade_note_service(db, user_id=1, trade_id=20, note="x")
        assert str(exc_info.value) == "Trade not found"
        mock_get.assert_called_once_with(db, 20)


def test_update_trade_note_success_and_none_becomes_empty() -> None:
    existing_trade = SimpleNamespace(
        id=20,
        user_id=1,
        friendly_name="Trade",
        symbol="AAPL",
        exchange_id=1,
        underlying_currency=dto.UnderlyingCurrency.USD,
        trade_type=dto.TradeType.LONG_SPOT,
        trade_strategy=dto.TradeStrategy.SPOT,
        trade_date=datetime.now(timezone.utc).date(),
        trade_time_utc=None,
        expiry_date=None,
        strike_price_cents=None,
        quantity=1,
        quantity_multiplier=1,
        price_cents=1000,
        gross_cash_flow_cents=-1000,
        commission_cents=10,
        net_cash_flow_cents=-1010,
        is_invalidated=False,
        invalidated_at=None,
        replaced_by_trade_id=None,
        notes="old",
        cycle_id=None,
    )
    updated_trade = SimpleNamespace(**{**existing_trade.__dict__, "notes": ""})
    with (
        FakeDBFactory().get_session_ctx_manager() as db,
        patch("trading_journal.crud.get_trade_by_id", return_value=existing_trade) as mock_get,
        patch("trading_journal.crud.update_trade_note", return_value=updated_trade) as mock_update,
    ):
        res = service.update_trade_note_service(db, user_id=1, trade_id=20, note=None)
        assert res.notes == ""
        mock_get.assert_called_once_with(db, 20)
        mock_update.assert_called_once_with(db, 20, "")
