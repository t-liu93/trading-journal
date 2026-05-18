"""Strategy-specific 1:1 extensions of ``Position`` (data-model.md §4.8)."""

import uuid
from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base
from trading_journal.models._enums import FundingSource, enum_values


class WheelCycleMeta(Base):
    __tablename__ = "wheel_cycle_metas"

    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("positions.id", ondelete="cascade"), primary_key=True
    )
    funding_source: Mapped[FundingSource] = mapped_column(
        SAEnum(
            FundingSource,
            name="funding_source",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    loan_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    interest_rate_apr: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    interest_accrued: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)


class PmccCycleMeta(Base):
    __tablename__ = "pmcc_cycle_metas"

    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("positions.id", ondelete="cascade"), primary_key=True
    )
    leap_instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instruments.id", ondelete="restrict"),
        nullable=False,
    )
