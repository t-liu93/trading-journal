"""``StrategyConfig`` API I/O schemas (data-model.md §4.7).

Validation choices:
  - ``exposure_currency`` is a 3-letter ISO 4217 code; we enforce the format
    (``^[A-Z]{3}$``) but not a whitelist.
  - ``max_exposure`` is nullable — ``None`` means "no cap yet". When present
    it must be strictly positive (``gt=0``). Pydantic v2 skips the ``gt``
    constraint when the value is ``None``.
  - ``model_config = ConfigDict(extra="forbid")`` on Create and Update
    rejects typos with 422.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import StrategyType

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class StrategyConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_type: StrategyType
    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str = Field(pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_type: StrategyType
    max_exposure: Decimal | None
    exposure_currency: str
    notes: str | None
    updated_at: datetime
