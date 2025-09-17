from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from trading_journal import models


def _check_enum(enum_cls, value, field_name: str):
    if value is None:
        raise ValueError(f"{field_name} is required")
    # already an enum member
    if isinstance(value, enum_cls):
        return value
    # strict string match: must match exactly enum name or enum value (case-sensitive)
    if isinstance(value, str):
        for m in enum_cls:
            if m.name == value or str(m.value) == value:
                return m
    allowed = [m.name for m in enum_cls]
    raise ValueError(f"Invalid {field_name!s}: {value!r}. Allowed: {allowed}")


# Trades
def create_trade(session: Session, trade_data: Mapping) -> models.Trades:
    if hasattr(trade_data, "dict"):
        data = trade_data.dict(exclude_unset=True)
    else:
        data = dict(trade_data)
    allowed = {c.name for c in models.Trades.__table__.columns}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "symbol" not in payload:
        raise ValueError("symbol is required")
    if "underlying_currency" not in payload:
        raise ValueError("underlying_currency is required")
    payload["underlying_currency"] = _check_enum(
        models.UnderlyingCurrency, payload["underlying_currency"], "underlying_currency"
    )
    if "trade_type" not in payload:
        raise ValueError("trade_type is required")
    payload["trade_type"] = _check_enum(
        models.TradeType, payload["trade_type"], "trade_type"
    )
    if "trade_strategy" not in payload:
        raise ValueError("trade_strategy is required")
    payload["trade_strategy"] = _check_enum(
        models.TradeStrategy, payload["trade_strategy"], "trade_strategy"
    )
    now = datetime.now(timezone.utc)
    payload.pop("trade_time_utc", None)
    payload["trade_time_utc"] = now
    if "trade_date" not in payload or payload.get("trade_date") is None:
        payload["trade_date"] = payload["trade_time_utc"].date()
    cycle_id = payload.get("cycle_id")
    user_id = payload.get("user_id")
    if "quantity" not in payload:
        raise ValueError("quantity is required")
    if "price_cents" not in payload:
        raise ValueError("price_cents is required")
    if "commission_cents" not in payload:
        payload["commission_cents"] = 0
    quantity: int = payload["quantity"]
    price_cents: int = payload["price_cents"]
    commission_cents: int = payload["commission_cents"]
    if "gross_cash_flow_cents" not in payload:
        payload["gross_cash_flow_cents"] = -quantity * price_cents
    if "net_cash_flow_cents" not in payload:
        payload["net_cash_flow_cents"] = (
            payload["gross_cash_flow_cents"] - commission_cents
        )
    if cycle_id is None:
        cycle_id = create_cycle(
            session,
            {
                "user_id": user_id,
                "symbol": payload["symbol"],
                "underlying_currency": payload["underlying_currency"],
                "friendly_name": "Auto-created Cycle by trade "
                + payload.get("friendly_name", ""),
                "status": models.CycleStatus.OPEN,
                "start_date": payload["trade_date"],
            },
        ).id
        payload["cycle_id"] = cycle_id
    if cycle_id is not None:
        cycle = session.get(models.Cycles, cycle_id)
        if cycle is None:
            raise ValueError("cycle_id does not exist")
        else:
            if cycle.user_id != user_id:
                raise ValueError("cycle.user_id does not match trade.user_id")
    t = models.Trades(**payload)
    session.add(t)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_trade integrity error") from e
    session.refresh(t)
    return t


def get_trade_by_id(session: Session, trade_id: int) -> models.Trades | None:
    return session.get(models.Trades, trade_id)


def get_trade_by_user_id_and_friendly_name(
    session: Session, user_id: int, friendly_name: str
) -> models.Trades | None:
    statement = select(models.Trades).where(
        models.Trades.user_id == user_id,
        models.Trades.friendly_name == friendly_name,
    )
    return session.exec(statement).first()


def get_trades_by_user_id(session: Session, user_id: int) -> list[models.Trades]:
    statement = select(models.Trades).where(
        models.Trades.user_id == user_id,
    )
    return session.exec(statement).all()


# Cycles
def create_cycle(session: Session, cycle_data: Mapping) -> models.Cycles:
    if hasattr(cycle_data, "dict"):
        data = cycle_data.dict(exclude_unset=True)
    else:
        data = dict(cycle_data)
    allowed = {c.name for c in models.Cycles.__table__.columns}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "user_id" not in payload:
        raise ValueError("user_id is required")
    if "symbol" not in payload:
        raise ValueError("symbol is required")
    if "underlying_currency" not in payload:
        raise ValueError("underlying_currency is required")
    payload["underlying_currency"] = _check_enum(
        models.UnderlyingCurrency, payload["underlying_currency"], "underlying_currency"
    )
    if "status" not in payload:
        raise ValueError("status is required")
    payload["status"] = _check_enum(models.CycleStatus, payload["status"], "status")
    if "start_date" not in payload:
        raise ValueError("start_date is required")

    c = models.Cycles(**payload)
    session.add(c)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_cycle integrity error") from e
    session.refresh(c)
    return c


# Users
def create_user(session: Session, user_data: Mapping) -> models.Users:
    if hasattr(user_data, "dict"):
        data = user_data.dict(exclude_unset=True)
    else:
        data = dict(user_data)
    allowed = {c.name for c in models.Users.__table__.columns}
    payload = {k: v for k, v in data.items() if k in allowed}
    if "username" not in payload:
        raise ValueError("username is required")
    if "password_hash" not in payload:
        raise ValueError("password_hash is required")

    u = models.Users(**payload)
    session.add(u)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_user integrity error") from e
    session.refresh(u)
    return u
