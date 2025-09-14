from typing import Mapping

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from trading_journal import models


def _coerce_enum(enum_cls, value, field_name: str):
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
    if "trade_type" not in payload:
        raise ValueError("trade_type is required")
    payload["trade_type"] = _coerce_enum(
        models.TradeType, payload["trade_type"], "trade_type"
    )

    if "trade_strategy" not in payload:
        raise ValueError("trade_strategy is required")
    payload["trade_strategy"] = _coerce_enum(
        models.TradeStrategy, payload["trade_strategy"], "trade_strategy"
    )
    cycle_id = payload.get("cycle_id")
    user_id = payload.get("user_id")

    if cycle_id is not None:
        cycle = session.get(models.Cycles, cycle_id)
        if cycle is None:
            pass  # TODO: create a cycle with basic info here
        else:
            if cycle.user_id != user_id:
                raise ValueError("cycle.user_id does not match trade.user_id")
    else:
        raise ValueError("trade must have a cycle_id.")
    t = models.Trades(**payload)
    session.add(t)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("create_trade integrity error") from e
    session.refresh(t)
    return t
