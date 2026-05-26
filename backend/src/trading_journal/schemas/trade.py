"""``Trade`` API I/O schemas (data-model.md §4.5, P9)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import TradeAction


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    executed_at: datetime
    order_group_id: uuid.UUID | None = None
    notes: str | None = None


class TradeUpdate(BaseModel):
    """Only ``notes`` may change. To amend numeric data, archive + re-POST."""

    model_config = ConfigDict(extra="forbid")

    notes: str | None = None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    account_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal
    price: Decimal
    commission: Decimal
    fees: Decimal
    cash_flow: Decimal
    executed_at: datetime
    order_group_id: uuid.UUID | None
    broker_trade_id: str | None
    notes: str | None
    archived_at: datetime | None


TradeCreatePayload = TradeCreate | list[TradeCreate]
