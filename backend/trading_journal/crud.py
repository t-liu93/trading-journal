from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from trading_journal import models

if TYPE_CHECKING:
    from collections.abc import Mapping
    from enum import Enum


# Generic enum member type
T = TypeVar("T", bound="Enum")


def _check_enum(enum_cls: type[T], value: object, field_name: str) -> T:
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


def _allowed_columns(model: type[models.SQLModel]) -> set[str]:
    tbl = cast("models.SQLModel", model).__table__  # type: ignore[attr-defined]
    return {c.name for c in tbl.columns}


AnyModel = Any


def _data_to_dict(data: AnyModel) -> dict[str, AnyModel]:
    if isinstance(data, BaseModel):
        return data.model_dump(exclude_unset=True)
    if hasattr(data, "dict"):
        return data.dict(exclude_unset=True)
    return dict(data)


# Trades
def create_trade(session: Session, trade_data: Mapping[str, Any] | BaseModel) -> models.Trades:
    data = _data_to_dict(trade_data)
    allowed = _allowed_columns(models.Trades)
    payload = {k: v for k, v in data.items() if k in allowed}
    cycle_id = payload.get("cycle_id")
    if "symbol" not in payload:
        raise ValueError("symbol is required")
    if "exchange_id" not in payload and cycle_id is None:
        raise ValueError("exchange_id is required when no cycle is attached")
    # If an exchange_id is provided (and no cycle is attached), ensure the exchange exists
    # and belongs to the same user as the trade (if user_id is provided).
    if cycle_id is None and "exchange_id" in payload:
        ex = session.get(models.Exchanges, payload["exchange_id"])
        if ex is None:
            raise ValueError("exchange_id does not exist")
        user_id = payload.get("user_id")
        if user_id is not None and ex.user_id != user_id:
            raise ValueError("exchange.user_id does not match trade.user_id")
    if "underlying_currency" not in payload:
        raise ValueError("underlying_currency is required")
    payload["underlying_currency"] = _check_enum(models.UnderlyingCurrency, payload["underlying_currency"], "underlying_currency")
    if "trade_type" not in payload:
        raise ValueError("trade_type is required")
    payload["trade_type"] = _check_enum(models.TradeType, payload["trade_type"], "trade_type")
    if "trade_strategy" not in payload:
        raise ValueError("trade_strategy is required")
    payload["trade_strategy"] = _check_enum(models.TradeStrategy, payload["trade_strategy"], "trade_strategy")
    # trade_time_utc is the creation moment: always set to now (caller shouldn't provide)
    now = datetime.now(timezone.utc)
    payload.pop("trade_time_utc", None)
    payload["trade_time_utc"] = now
    if "trade_date" not in payload or payload.get("trade_date") is None:
        payload["trade_date"] = payload["trade_time_utc"].date()
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
        payload["net_cash_flow_cents"] = payload["gross_cash_flow_cents"] - commission_cents

    # If no cycle_id provided, create Cycle instance but don't call create_cycle()
    created_cycle = None
    if cycle_id is None:
        c_payload = {
            "user_id": user_id,
            "symbol": payload["symbol"],
            "exchange_id": payload["exchange_id"],
            "underlying_currency": payload["underlying_currency"],
            "friendly_name": "Auto-created Cycle by trade " + payload.get("friendly_name", ""),
            "status": models.CycleStatus.OPEN,
            "start_date": payload["trade_date"],
        }
        created_cycle = models.Cycles(**c_payload)
        session.add(created_cycle)
        # do NOT flush here; will flush together with trade below

    # If cycle_id provided, validate existence and ownership
    if cycle_id is not None:
        cycle = session.get(models.Cycles, cycle_id)

        if cycle is None:
            raise ValueError("cycle_id does not exist")
        payload.pop("exchange_id", None)  # ignore exchange_id if provided; use cycle's exchange_id
        payload["exchange_id"] = cycle.exchange_id
        if cycle.user_id != user_id:
            raise ValueError("cycle.user_id does not match trade.user_id")

    # Build trade instance; if we created a Cycle instance, link via relationship so a single flush will persist both and populate ids
    t_payload = dict(payload)
    # remove cycle_id if we're using created_cycle; relationship will set it on flush
    if created_cycle is not None:
        t_payload.pop("cycle_id", None)
    t = models.Trades(**t_payload)
    if created_cycle is not None:
        t.cycle = created_cycle

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


def get_trade_by_user_id_and_friendly_name(session: Session, user_id: int, friendly_name: str) -> models.Trades | None:
    statement = select(models.Trades).where(
        models.Trades.user_id == user_id,
        models.Trades.friendly_name == friendly_name,
    )
    return session.exec(statement).first()


def get_trades_by_user_id(session: Session, user_id: int) -> list[models.Trades]:
    statement = select(models.Trades).where(
        models.Trades.user_id == user_id,
    )
    return list(session.exec(statement).all())


def update_trade_note(session: Session, trade_id: int, note: str) -> models.Trades:
    trade: models.Trades | None = session.get(models.Trades, trade_id)
    if trade is None:
        raise ValueError("trade_id does not exist")
    trade.notes = note
    session.add(trade)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("update_trade_note integrity error") from e
    session.refresh(trade)
    return trade


def invalidate_trade(session: Session, trade_id: int) -> models.Trades:
    trade: models.Trades | None = session.get(models.Trades, trade_id)
    if trade is None:
        raise ValueError("trade_id does not exist")
    if trade.is_invalidated:
        raise ValueError("trade is already invalidated")
    trade.is_invalidated = True
    trade.invalidated_at = datetime.now(timezone.utc)
    session.add(trade)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("invalidate_trade integrity error") from e
    session.refresh(trade)
    return trade


def replace_trade(session: Session, old_trade_id: int, new_trade_data: Mapping[str, Any] | BaseModel) -> models.Trades:
    invalidate_trade(session, old_trade_id)
    data = _data_to_dict(new_trade_data)
    data["replaced_by_trade_id"] = old_trade_id
    return create_trade(session, data)


# Cycles
def create_cycle(session: Session, cycle_data: Mapping[str, Any] | BaseModel) -> models.Cycles:
    data = _data_to_dict(cycle_data)
    allowed = _allowed_columns(models.Cycles)
    payload = {k: v for k, v in data.items() if k in allowed}
    if "user_id" not in payload:
        raise ValueError("user_id is required")
    if "symbol" not in payload:
        raise ValueError("symbol is required")
    if "exchange_id" not in payload:
        raise ValueError("exchange_id is required")
    # ensure the exchange exists and belongs to the same user
    ex = session.get(models.Exchanges, payload["exchange_id"])
    if ex is None:
        raise ValueError("exchange_id does not exist")
    if ex.user_id != payload.get("user_id"):
        raise ValueError("exchange.user_id does not match cycle.user_id")
    if "underlying_currency" not in payload:
        raise ValueError("underlying_currency is required")
    payload["underlying_currency"] = _check_enum(models.UnderlyingCurrency, payload["underlying_currency"], "underlying_currency")
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


IMMUTABLE_CYCLE_FIELDS = {"id", "user_id", "start_date", "created_at"}


def update_cycle(session: Session, cycle_id: int, update_data: Mapping[str, Any] | BaseModel) -> models.Cycles:
    cycle: models.Cycles | None = session.get(models.Cycles, cycle_id)
    if cycle is None:
        raise ValueError("cycle_id does not exist")
    data = _data_to_dict(update_data)

    allowed = _allowed_columns(models.Cycles)
    for k, v in data.items():
        if k in IMMUTABLE_CYCLE_FIELDS:
            raise ValueError(f"field {k!r} is immutable")
        if k not in allowed:
            continue
        # If trying to change exchange_id, ensure the new exchange exists and belongs to
        # the same user as the cycle.
        if k == "exchange_id":
            ex = session.get(models.Exchanges, v)
            if ex is None:
                raise ValueError("exchange_id does not exist")
            if ex.user_id != cycle.user_id:
                raise ValueError("exchange.user_id does not match cycle.user_id")
        if k == "underlying_currency":
            v = _check_enum(models.UnderlyingCurrency, v, "underlying_currency")  # noqa: PLW2901
        if k == "status":
            v = _check_enum(models.CycleStatus, v, "status")  # noqa: PLW2901
        setattr(cycle, k, v)
    session.add(cycle)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("update_cycle integrity error") from e
    session.refresh(cycle)
    return cycle


# Exchanges
IMMUTABLE_EXCHANGE_FIELDS = {"id"}


def create_exchange(session: Session, exchange_data: Mapping[str, Any] | BaseModel) -> models.Exchanges:
    data = _data_to_dict(exchange_data)
    allowed = _allowed_columns(models.Exchanges)
    payload = {k: v for k, v in data.items() if k in allowed}
    if "name" not in payload:
        raise ValueError("name is required")

    e = models.Exchanges(**payload)
    session.add(e)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_exchange integrity error") from e
    session.refresh(e)
    return e


def get_exchange_by_id(session: Session, exchange_id: int) -> models.Exchanges | None:
    return session.get(models.Exchanges, exchange_id)


def get_exchange_by_name_and_user_id(session: Session, name: str, user_id: int) -> models.Exchanges | None:
    statement = select(models.Exchanges).where(
        models.Exchanges.name == name,
        models.Exchanges.user_id == user_id,
    )
    return session.exec(statement).first()


def get_all_exchanges(session: Session) -> list[models.Exchanges]:
    statement = select(models.Exchanges)
    return list(session.exec(statement).all())


def get_all_exchanges_by_user_id(session: Session, user_id: int) -> list[models.Exchanges]:
    statement = select(models.Exchanges).where(
        models.Exchanges.user_id == user_id,
    )
    return list(session.exec(statement).all())


def update_exchange(session: Session, exchange_id: int, update_data: Mapping[str, Any] | BaseModel) -> models.Exchanges:
    exchange: models.Exchanges | None = session.get(models.Exchanges, exchange_id)
    if exchange is None:
        raise ValueError("exchange_id does not exist")
    data = _data_to_dict(update_data)
    allowed = _allowed_columns(models.Exchanges)
    for k, v in data.items():
        if k in IMMUTABLE_EXCHANGE_FIELDS:
            raise ValueError(f"field {k!r} is immutable")
        if k in allowed:
            setattr(exchange, k, v)
    session.add(exchange)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("update_exchange integrity error") from e
    session.refresh(exchange)
    return exchange


def delete_exchange(session: Session, exchange_id: int) -> None:
    exchange: models.Exchanges | None = session.get(models.Exchanges, exchange_id)
    if exchange is None:
        return
    session.delete(exchange)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("delete_exchange integrity error") from e


# Users
IMMUTABLE_USER_FIELDS = {"id", "username", "created_at"}


def create_user(session: Session, user_data: Mapping[str, Any] | BaseModel) -> models.Users:
    data = _data_to_dict(user_data)
    allowed = _allowed_columns(models.Users)
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


def get_user_by_id(session: Session, user_id: int) -> models.Users | None:
    return session.get(models.Users, user_id)


def get_user_by_username(session: Session, username: str) -> models.Users | None:
    statement = select(models.Users).where(
        models.Users.username == username,
    )
    return session.exec(statement).first()


def update_user(session: Session, user_id: int, update_data: Mapping[str, Any] | BaseModel) -> models.Users:
    user: models.Users | None = session.get(models.Users, user_id)
    if user is None:
        raise ValueError("user_id does not exist")
    data = _data_to_dict(update_data)
    allowed = _allowed_columns(models.Users)
    for k, v in data.items():
        if k in IMMUTABLE_USER_FIELDS:
            raise ValueError(f"field {k!r} is immutable")
        if k in allowed:
            setattr(user, k, v)
    session.add(user)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("update_user integrity error") from e
    session.refresh(user)
    return user


# Sessions
def create_login_session(
    session: Session,
    user_id: int,
    session_token_hash: str,
    session_length_seconds: int = 86400,
    last_used_ip: str | None = None,
    user_agent: str | None = None,
    device_name: str | None = None,
) -> models.Sessions:
    user: models.Users | None = session.get(models.Users, user_id)
    if user is None:
        raise ValueError("user_id does not exist")
    user_id_val = cast("int", user.id)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=session_length_seconds)
    s = models.Sessions(
        user_id=user_id_val,
        session_token_hash=session_token_hash,
        created_at=now,
        expires_at=expires_at,
        last_seen_at=now,
        last_used_ip=last_used_ip,
        user_agent=user_agent,
        device_name=device_name,
    )
    session.add(s)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_login_session integrity error") from e
    session.refresh(s)
    return s


def get_login_session_by_token_hash_and_user_id(session: Session, session_token_hash: str, user_id: int) -> models.Sessions | None:
    statement = select(models.Sessions).where(
        models.Sessions.session_token_hash == session_token_hash,
        models.Sessions.user_id == user_id,
        models.Sessions.expires_at > datetime.now(timezone.utc),
    )

    return session.exec(statement).first()


def get_login_session_by_token_hash(session: Session, session_token_hash: str) -> models.Sessions | None:
    statement = select(models.Sessions).where(
        models.Sessions.session_token_hash == session_token_hash,
        models.Sessions.expires_at > datetime.now(timezone.utc),
    )

    return session.exec(statement).first()


IMMUTABLE_SESSION_FIELDS = {"id", "user_id", "session_token_hash", "created_at"}


def update_login_session(session: Session, session_token_hashed: str, update_session: Mapping[str, Any] | BaseModel) -> models.Sessions | None:
    login_session: models.Sessions | None = session.exec(
        select(models.Sessions).where(
            models.Sessions.session_token_hash == session_token_hashed,
            models.Sessions.expires_at > datetime.now(timezone.utc),
        ),
    ).first()
    if login_session is None:
        return None
    data = _data_to_dict(update_session)
    allowed = _allowed_columns(models.Sessions)
    for k, v in data.items():
        if k in allowed and k not in IMMUTABLE_SESSION_FIELDS:
            setattr(login_session, k, v)
    session.add(login_session)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("update_login_session integrity error") from e
    session.refresh(login_session)
    return login_session


def delete_login_session(session: Session, session_token_hash: str) -> None:
    login_session: models.Sessions | None = session.exec(
        select(models.Sessions).where(
            models.Sessions.session_token_hash == session_token_hash,
        ),
    ).first()
    if login_session is None:
        return
    session.delete(login_session)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("delete_login_session integrity error") from e
