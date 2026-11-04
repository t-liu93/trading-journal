"""Strict structured inputs and outputs for MCP entry preparation."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import StrategyType, TradeAction
from trading_journal.schemas.instrument import InstrumentCreate


class ExistingInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: uuid.UUID


class PendingInstrument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pending: InstrumentCreate


InstrumentReference = Annotated[
    ExistingInstrument | PendingInstrument, Field(union_mode="left_to_right")
]


class EntryLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument: InstrumentReference
    action: TradeAction
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    executed_at: datetime
    timezone: str | None = None
    commission: Decimal | None = Field(default=None, ge=0)
    fees: Decimal | None = Field(default=None, ge=0)
    order_group_id: uuid.UUID | None = None
    notes: str | None = None


class OpenPositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: uuid.UUID
    primary_instrument: InstrumentReference
    strategy_type: StrategyType
    opened_at: datetime | None = None
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PrepareEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    kind: Literal["open_position", "add_trades"]
    legs: list[EntryLeg] = Field(min_length=1)
    position: OpenPositionInput | None = None
    position_id: uuid.UUID | None = None


class EntryPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: uuid.UUID
    request_id: uuid.UUID
    expires_at: datetime
    preview: dict[str, object]
    defaults: dict[str, object]
