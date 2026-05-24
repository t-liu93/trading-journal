"""``Instrument`` API I/O schemas (data-model.md §4.3).

Validation = format only (no factual "is this a real ticker" check — P6.x).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trading_journal.models._enums import InstrumentKind, OptionStyle, OptType

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class StockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stock"]
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY_PATTERN)

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("symbol must not be blank")
        return stripped


class OptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["option"]
    underlying_symbol: str = Field(min_length=1, max_length=64)
    underlying_exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY_PATTERN)
    opt_type: OptType
    strike: Decimal = Field(gt=0)
    expiry: date
    multiplier: int = Field(default=100, gt=0)
    style: OptionStyle = OptionStyle.AMERICAN

    @field_validator("underlying_symbol")
    @classmethod
    def symbol_must_be_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("underlying_symbol must not be blank")
        return stripped


class ForexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["forex"]
    symbol: str = Field(min_length=1, max_length=64)
    base_currency: str = Field(pattern=CURRENCY_PATTERN)
    quote_currency: str = Field(pattern=CURRENCY_PATTERN)
    pip_size: Decimal = Field(gt=0)
    contract_size: Decimal | None = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_non_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("symbol must not be blank")
        return stripped


InstrumentCreate = Annotated[
    StockCreate | OptionCreate | ForexCreate, Field(discriminator="kind")
]


class OptionContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    underlying_id: uuid.UUID
    opt_type: OptType
    strike: Decimal
    expiry: date
    multiplier: int
    style: OptionStyle


class ForexPairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_currency: str
    quote_currency: str
    pip_size: Decimal
    contract_size: Decimal | None


class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: InstrumentKind
    symbol: str
    exchange: str | None
    currency: str
    created_at: datetime
    option: OptionContractRead | None = None
    forex: ForexPairRead | None = None
