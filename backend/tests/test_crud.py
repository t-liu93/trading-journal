from collections.abc import Generator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from trading_journal import crud, models


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(e)
    try:
        yield e
    finally:
        SQLModel.metadata.drop_all(e)
        SQLModel.metadata.clear()
        e.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as s:
        yield s


def make_user(session: Session, username: str = "testuser") -> int:
    user = models.Users(username=username, password_hash="hashedpassword")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id


def make_cycle(session, user_id: int, friendly_name: str = "Test Cycle") -> int:
    cycle = models.Cycles(
        user_id=user_id,
        friendly_name=friendly_name,
        symbol="AAPL",
        underlying_currency="USD",
        status=models.CycleStatus.OPEN,
        start_date=datetime.now().date(),
    )
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    return cycle.id


def test_create_trade_success(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)

    trade_data = {
        "user_id": user_id,
        "friendly_name": "Test Trade",
        "symbol": "AAPL",
        "underlying_currency": "USD",
        "trade_type": "LONG_SPOT",
        "trade_strategy": "SPOT",
        "trade_time_utc": datetime.now(),
        "quantity": 10,
        "price_cents": 15000,
        "gross_cash_flow_cents": -150000,
        "commission_cents": 500,
        "net_cash_flow_cents": -150500,
        "cycle_id": cycle_id,
    }

    trade = crud.create_trade(session, trade_data)
    assert trade.id is not None
    assert trade.user_id == user_id
    assert trade.cycle_id == cycle_id
