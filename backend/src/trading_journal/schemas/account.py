"""``Account`` API I/O schemas (data-model.md §4.2).

Validation choices:
  - ``base_currency`` is a 3-letter ISO 4217 code; we enforce the format
    (``^[A-Z]{3}$``) but not a whitelist — common non-ISO codes (e.g. ``BTC``)
    are intentionally permitted.
  - ``model_config = ConfigDict(extra="forbid")`` on both Create and Update
    rejects typos with 422 instead of silently ignoring them.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import AccountType

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    broker: str = Field(min_length=1, max_length=255)
    account_type: AccountType
    base_currency: str = Field(min_length=3, max_length=3, pattern=CURRENCY_PATTERN)
    notes: str | None = None


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    broker: str | None = Field(default=None, min_length=1, max_length=255)
    account_type: AccountType | None = None
    base_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=CURRENCY_PATTERN
    )
    notes: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    broker: str
    account_type: AccountType
    base_currency: str
    notes: str | None
    created_at: datetime
    archived_at: datetime | None
