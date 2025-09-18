from collections.abc import Generator
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from trading_journal import crud, models

# TODO: If needed, add failing flow tests, but now only add happy flow.


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
        underlying_currency=models.UnderlyingCurrency.USD,
        status=models.CycleStatus.OPEN,
        start_date=datetime.now().date(),
    )
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    return cycle.id


def make_trade(
    session, user_id: int, cycle_id: int, friendly_name: str = "Test Trade"
) -> int:
    trade = models.Trades(
        user_id=user_id,
        friendly_name=friendly_name,
        symbol="AAPL",
        underlying_currency=models.UnderlyingCurrency.USD,
        trade_type=models.TradeType.LONG_SPOT,
        trade_strategy=models.TradeStrategy.SPOT,
        trade_date=datetime.now().date(),
        trade_time_utc=datetime.now(),
        quantity=10,
        price_cents=15000,
        gross_cash_flow_cents=-150000,
        commission_cents=500,
        net_cash_flow_cents=-150500,
        cycle_id=cycle_id,
        notes="Initial test trade",
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade.id


def make_trade_by_trade_data(session, trade_data: dict) -> int:
    trade = models.Trades(**trade_data)
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade.id


def test_create_trade_success_with_cycle(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)

    trade_data = {
        "user_id": user_id,
        "friendly_name": "Test Trade",
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
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
    session.refresh(trade)

    actual_trade = session.get(models.Trades, trade.id)
    assert actual_trade is not None
    assert actual_trade.friendly_name == trade_data["friendly_name"]
    assert actual_trade.symbol == trade_data["symbol"]
    assert actual_trade.underlying_currency == trade_data["underlying_currency"]
    assert actual_trade.trade_type == trade_data["trade_type"]
    assert actual_trade.trade_strategy == trade_data["trade_strategy"]
    assert actual_trade.quantity == trade_data["quantity"]
    assert actual_trade.price_cents == trade_data["price_cents"]
    assert actual_trade.gross_cash_flow_cents == trade_data["gross_cash_flow_cents"]
    assert actual_trade.commission_cents == trade_data["commission_cents"]
    assert actual_trade.net_cash_flow_cents == trade_data["net_cash_flow_cents"]
    assert actual_trade.cycle_id == trade_data["cycle_id"]


def test_create_trade_with_auto_created_cycle(session: Session):
    user_id = make_user(session)

    trade_data = {
        "user_id": user_id,
        "friendly_name": "Test Trade with Auto Cycle",
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_time_utc": datetime.now(),
        "quantity": 5,
        "price_cents": 15500,
    }

    trade = crud.create_trade(session, trade_data)
    assert trade.id is not None
    assert trade.user_id == user_id
    assert trade.cycle_id is not None
    session.refresh(trade)

    actual_trade = session.get(models.Trades, trade.id)
    assert actual_trade is not None
    assert actual_trade.friendly_name == trade_data["friendly_name"]
    assert actual_trade.symbol == trade_data["symbol"]
    assert actual_trade.underlying_currency == trade_data["underlying_currency"]
    assert actual_trade.trade_type == trade_data["trade_type"]
    assert actual_trade.trade_strategy == trade_data["trade_strategy"]
    assert actual_trade.quantity == trade_data["quantity"]
    assert actual_trade.price_cents == trade_data["price_cents"]
    assert actual_trade.cycle_id == trade.cycle_id

    # Verify the auto-created cycle
    auto_cycle = session.get(models.Cycles, trade.cycle_id)
    assert auto_cycle is not None
    assert auto_cycle.user_id == user_id
    assert auto_cycle.symbol == trade_data["symbol"]
    assert auto_cycle.underlying_currency == trade_data["underlying_currency"]
    assert auto_cycle.status == models.CycleStatus.OPEN
    assert auto_cycle.friendly_name.startswith("Auto-created Cycle by trade")


def test_create_trade_missing_required_fields(session: Session):
    user_id = make_user(session)

    base_trade_data = {
        "user_id": user_id,
        "friendly_name": "Incomplete Trade",
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_time_utc": datetime.now(),
        "quantity": 10,
        "price_cents": 15000,
    }

    # Missing symbol
    trade_data = base_trade_data.copy()
    trade_data.pop("symbol", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "symbol is required" in str(excinfo.value)

    # Missing underlying_currency
    trade_data = base_trade_data.copy()
    trade_data.pop("underlying_currency", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "underlying_currency is required" in str(excinfo.value)

    # Missing trade_type
    trade_data = base_trade_data.copy()
    trade_data.pop("trade_type", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "trade_type is required" in str(excinfo.value)

    # Missing trade_strategy
    trade_data = base_trade_data.copy()
    trade_data.pop("trade_strategy", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "trade_strategy is required" in str(excinfo.value)

    # Missing quantity
    trade_data = base_trade_data.copy()
    trade_data.pop("quantity", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "quantity is required" in str(excinfo.value)

    # Missing price_cents
    trade_data = base_trade_data.copy()
    trade_data.pop("price_cents", None)
    with pytest.raises(ValueError) as excinfo:
        crud.create_trade(session, trade_data)
    assert "price_cents is required" in str(excinfo.value)


def test_get_trade_by_id(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    trade_data = {
        "user_id": user_id,
        "friendly_name": "Test Trade for Get",
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_date": datetime.now().date(),
        "trade_time_utc": datetime.now(),
        "quantity": 10,
        "price_cents": 15000,
        "gross_cash_flow_cents": -150000,
        "commission_cents": 500,
        "net_cash_flow_cents": -150500,
        "cycle_id": cycle_id,
    }
    trade_id = make_trade_by_trade_data(session, trade_data)
    trade = crud.get_trade_by_id(session, trade_id)
    assert trade is not None
    assert trade.id == trade_id
    assert trade.friendly_name == trade_data["friendly_name"]
    assert trade.symbol == trade_data["symbol"]
    assert trade.underlying_currency == trade_data["underlying_currency"]
    assert trade.trade_type == trade_data["trade_type"]
    assert trade.trade_strategy == trade_data["trade_strategy"]
    assert trade.quantity == trade_data["quantity"]
    assert trade.price_cents == trade_data["price_cents"]
    assert trade.gross_cash_flow_cents == trade_data["gross_cash_flow_cents"]
    assert trade.commission_cents == trade_data["commission_cents"]
    assert trade.net_cash_flow_cents == trade_data["net_cash_flow_cents"]
    assert trade.cycle_id == trade_data["cycle_id"]
    assert trade.trade_date == trade_data["trade_date"]


def test_get_trade_by_user_id_and_friendly_name(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    friendly_name = "Unique Trade Name"
    trade_data = {
        "user_id": user_id,
        "friendly_name": friendly_name,
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_date": datetime.now().date(),
        "trade_time_utc": datetime.now(),
        "quantity": 10,
        "price_cents": 15000,
        "gross_cash_flow_cents": -150000,
        "commission_cents": 500,
        "net_cash_flow_cents": -150500,
        "cycle_id": cycle_id,
    }
    make_trade_by_trade_data(session, trade_data)
    trade = crud.get_trade_by_user_id_and_friendly_name(session, user_id, friendly_name)
    assert trade is not None
    assert trade.friendly_name == friendly_name
    assert trade.user_id == user_id


def test_get_trades_by_user_id(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    trade_data_1 = {
        "user_id": user_id,
        "friendly_name": "Trade One",
        "symbol": "AAPL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_date": datetime.now().date(),
        "trade_time_utc": datetime.now(),
        "quantity": 10,
        "price_cents": 15000,
        "gross_cash_flow_cents": -150000,
        "commission_cents": 500,
        "net_cash_flow_cents": -150500,
        "cycle_id": cycle_id,
    }
    trade_data_2 = {
        "user_id": user_id,
        "friendly_name": "Trade Two",
        "symbol": "GOOGL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.SHORT_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_date": datetime.now().date(),
        "trade_time_utc": datetime.now(),
        "quantity": 5,
        "price_cents": 280000,
        "gross_cash_flow_cents": 1400000,
        "commission_cents": 700,
        "net_cash_flow_cents": 1399300,
        "cycle_id": cycle_id,
    }
    make_trade_by_trade_data(session, trade_data_1)
    make_trade_by_trade_data(session, trade_data_2)

    trades = crud.get_trades_by_user_id(session, user_id)
    assert len(trades) == 2
    friendly_names = {trade.friendly_name for trade in trades}
    assert friendly_names == {"Trade One", "Trade Two"}


def test_update_trade_note(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    trade_id = make_trade(session, user_id, cycle_id)

    new_note = "This is an updated note."
    updated_trade = crud.update_trade_note(session, trade_id, new_note)
    assert updated_trade is not None
    assert updated_trade.id == trade_id
    assert updated_trade.notes == new_note

    session.refresh(updated_trade)
    actual_trade = session.get(models.Trades, trade_id)
    assert actual_trade is not None
    assert actual_trade.notes == new_note


def test_invalidate_trade(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    trade_id = make_trade(session, user_id, cycle_id)

    invalidated_trade = crud.invalidate_trade(session, trade_id)
    assert invalidated_trade is not None
    assert invalidated_trade.id == trade_id
    assert invalidated_trade.is_invalidated is True

    session.refresh(invalidated_trade)
    actual_trade = session.get(models.Trades, trade_id)
    assert actual_trade is not None
    assert actual_trade.is_invalidated is True


def test_replace_trade(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id)
    old_trade_id = make_trade(session, user_id, cycle_id)

    new_trade_data = {
        "user_id": user_id,
        "friendly_name": "Replaced Trade",
        "symbol": "MSFT",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "trade_type": models.TradeType.LONG_SPOT,
        "trade_strategy": models.TradeStrategy.SPOT,
        "trade_time_utc": datetime.now(),
        "quantity": 20,
        "price_cents": 25000,
    }

    new_trade = crud.replace_trade(session, old_trade_id, new_trade_data)
    assert new_trade.id is not None
    assert new_trade.id != old_trade_id
    assert new_trade.user_id == user_id
    assert new_trade.symbol == new_trade_data["symbol"]
    assert new_trade.quantity == new_trade_data["quantity"]

    # Verify the old trade is invalidated
    old_trade = session.get(models.Trades, old_trade_id)
    assert old_trade is not None
    assert old_trade.is_invalidated is True

    # Verify the new trade exists
    session.refresh(new_trade)
    actual_new_trade = session.get(models.Trades, new_trade.id)
    assert actual_new_trade is not None
    assert actual_new_trade.friendly_name == new_trade_data["friendly_name"]
    assert actual_new_trade.symbol == new_trade_data["symbol"]
    assert actual_new_trade.underlying_currency == new_trade_data["underlying_currency"]
    assert actual_new_trade.trade_type == new_trade_data["trade_type"]
    assert actual_new_trade.trade_strategy == new_trade_data["trade_strategy"]
    assert actual_new_trade.quantity == new_trade_data["quantity"]
    assert actual_new_trade.price_cents == new_trade_data["price_cents"]
    assert actual_new_trade.replaced_by_trade_id == old_trade_id


def test_create_cycle(session: Session):
    user_id = make_user(session)
    cycle_data = {
        "user_id": user_id,
        "friendly_name": "My First Cycle",
        "symbol": "GOOGL",
        "underlying_currency": models.UnderlyingCurrency.USD,
        "status": models.CycleStatus.OPEN,
        "start_date": datetime.now().date(),
    }
    cycle = crud.create_cycle(session, cycle_data)
    assert cycle.id is not None
    assert cycle.user_id == user_id
    assert cycle.friendly_name == cycle_data["friendly_name"]
    assert cycle.symbol == cycle_data["symbol"]
    assert cycle.underlying_currency == cycle_data["underlying_currency"]
    assert cycle.status == cycle_data["status"]
    assert cycle.start_date == cycle_data["start_date"]

    session.refresh(cycle)
    actual_cycle = session.get(models.Cycles, cycle.id)
    assert actual_cycle is not None
    assert actual_cycle.friendly_name == cycle_data["friendly_name"]
    assert actual_cycle.symbol == cycle_data["symbol"]
    assert actual_cycle.underlying_currency == cycle_data["underlying_currency"]
    assert actual_cycle.status == cycle_data["status"]
    assert actual_cycle.start_date == cycle_data["start_date"]


def test_update_cycle(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id, friendly_name="Initial Cycle Name")

    update_data = {
        "friendly_name": "Updated Cycle Name",
        "status": models.CycleStatus.CLOSED,
    }
    updated_cycle = crud.update_cycle(session, cycle_id, update_data)
    assert updated_cycle is not None
    assert updated_cycle.id == cycle_id
    assert updated_cycle.friendly_name == update_data["friendly_name"]
    assert updated_cycle.status == update_data["status"]

    session.refresh(updated_cycle)
    actual_cycle = session.get(models.Cycles, cycle_id)
    assert actual_cycle is not None
    assert actual_cycle.friendly_name == update_data["friendly_name"]
    assert actual_cycle.status == update_data["status"]


def test_update_cycle_immutable_fields(session: Session):
    user_id = make_user(session)
    cycle_id = make_cycle(session, user_id, friendly_name="Initial Cycle Name")

    # Attempt to update immutable fields
    update_data = {
        "id": cycle_id + 1,  # Trying to change the ID
        "user_id": user_id + 1,  # Trying to change the user_id
        "start_date": datetime(2020, 1, 1).date(),  # Trying to change start_date
        "created_at": datetime(2020, 1, 1),  # Trying to change created_at
        "friendly_name": "Valid Update",  # Valid field to update
    }

    with pytest.raises(ValueError) as excinfo:
        crud.update_cycle(session, cycle_id, update_data)
    assert (
        "field 'id' is immutable" in str(excinfo.value)
        or "field 'user_id' is immutable" in str(excinfo.value)
        or "field 'start_date' is immutable" in str(excinfo.value)
        or "field 'created_at' is immutable" in str(excinfo.value)
    )


def test_create_user(session: Session):
    user_data = {
        "username": "newuser",
        "password_hash": "newhashedpassword",
    }
    user = crud.create_user(session, user_data)
    assert user.id is not None
    assert user.username == user_data["username"]
    assert user.password_hash == user_data["password_hash"]

    session.refresh(user)
    actual_user = session.get(models.Users, user.id)
    assert actual_user is not None
    assert actual_user.username == user_data["username"]
    assert actual_user.password_hash == user_data["password_hash"]


def test_update_user(session: Session):
    user_id = make_user(session, username="updatableuser")

    update_data = {
        "password_hash": "updatedhashedpassword",
    }
    updated_user = crud.update_user(session, user_id, update_data)
    assert updated_user is not None
    assert updated_user.id == user_id
    assert updated_user.password_hash == update_data["password_hash"]

    session.refresh(updated_user)
    actual_user = session.get(models.Users, user_id)
    assert actual_user is not None
    assert actual_user.password_hash == update_data["password_hash"]


def test_update_user_immutable_fields(session: Session):
    user_id = make_user(session, username="immutableuser")

    # Attempt to update immutable fields
    update_data = {
        "id": user_id + 1,  # Trying to change the ID
        "username": "newusername",  # Trying to change the username
        "created_at": datetime(2020, 1, 1),  # Trying to change created_at
        "password_hash": "validupdate",  # Valid field to update
    }

    with pytest.raises(ValueError) as excinfo:
        crud.update_user(session, user_id, update_data)
    assert (
        "field 'id' is immutable" in str(excinfo.value)
        or "field 'username' is immutable" in str(excinfo.value)
        or "field 'created_at' is immutable" in str(excinfo.value)
    )
