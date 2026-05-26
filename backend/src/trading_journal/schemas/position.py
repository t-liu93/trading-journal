"""``Position`` API I/O schemas (data-model.md §4.4, P8)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import PositionStatus, StrategyType


class PositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    opened_at: datetime

    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PositionStatus | None = None
    closed_at: datetime | None = None
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    status: PositionStatus
    opened_at: datetime
    closed_at: datetime | None
    capital_used: Decimal | None
    max_risk_at_open: Decimal | None
    max_reward_at_open: Decimal | None
    pnl_realized: Decimal | None
    currency: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
