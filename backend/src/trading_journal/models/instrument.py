"""Polymorphic instrument tables (data-model.md §4.3).

``Instrument`` is the base. ``OptionContract`` and ``ForexPair`` are class-table
extensions keyed 1:1 by ``instrument_id``. Stocks need no extension table.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base
from trading_journal.models._enums import InstrumentKind, OptionStyle, OptType, enum_values


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[InstrumentKind] = mapped_column(
        SAEnum(
            InstrumentKind,
            name="instrument_kind",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OptionContract(Base):
    __tablename__ = "option_contracts"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="cascade"), primary_key=True
    )
    underlying_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instruments.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )
    opt_type: Mapped[OptType] = mapped_column(
        SAEnum(OptType, name="opt_type", native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    strike: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    style: Mapped[OptionStyle] = mapped_column(
        SAEnum(
            OptionStyle,
            name="option_style",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
        default=OptionStyle.AMERICAN,
    )


class ForexPair(Base):
    __tablename__ = "forex_pairs"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="cascade"), primary_key=True
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pip_size: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    contract_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
