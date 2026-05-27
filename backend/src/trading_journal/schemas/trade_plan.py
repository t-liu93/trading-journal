"""Pydantic schemas for TradePlan event stream (data-model.md §4.6)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TradePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_at: datetime
    planned_entry: Decimal | None = Field(default=None, gt=0)
    planned_stop_loss: Decimal | None = Field(default=None, gt=0)
    planned_take_profit: Decimal | None = Field(default=None, gt=0)
    target_rr: Decimal | None = Field(default=None, gt=0)
    thesis: str | None = None
    reason: str | None = None


class TradePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    revision_no: int
    effective_at: datetime
    planned_entry: Decimal | None
    planned_stop_loss: Decimal | None
    planned_take_profit: Decimal | None
    target_rr: Decimal | None
    thesis: str | None
    reason: str | None
    created_at: datetime
