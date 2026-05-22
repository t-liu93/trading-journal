"""``Instrument`` API I/O schemas (data-model.md §4.3).

P6.1 scaffold: stock create + read. Option and forex extension blocks
will be added in P6.2 / P6.3.

Validation = format only (no factual "is this a real ticker" check — P6.x).
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from trading_journal.models._enums import InstrumentKind

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


# P6.2 / P6.3 will add OptionCreate and ForexCreate to this union.
InstrumentCreate = Annotated[
    StockCreate, Field(discriminator="kind")
]


class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: InstrumentKind
    symbol: str
    exchange: str | None
    currency: str
    created_at: datetime
    # P6.2: option: OptionContractRead | None = None
    # P6.3: forex: ForexPairRead | None = None
