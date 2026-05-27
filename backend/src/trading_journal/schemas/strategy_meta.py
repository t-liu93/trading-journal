"""Pydantic schemas for WheelCycleMeta and PmccCycleMeta (data-model.md §4.8)."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import FundingSource

# ─────────────────── WheelCycleMeta ───────────────────


class WheelMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)


class WheelMetaUpdate(BaseModel):
    """Partial update; all fields optional. Numeric fields stay ``ge=0``."""

    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource | None = None
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)


class WheelMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    funding_source: FundingSource
    loan_amount: Decimal | None
    interest_rate_apr: Decimal | None
    interest_accrued: Decimal | None


# ─────────────────── PmccCycleMeta ───────────────────


class PmccMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID


class PmccMetaUpdate(BaseModel):
    """Partial update — ``leap_instrument_id`` is the only field."""

    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID | None = None


class PmccMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    leap_instrument_id: uuid.UUID
