"""``Position`` — the universal strategy-instance aggregate (data-model.md §4.4)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base
from trading_journal.models._enums import PositionStatus, StrategyType, enum_values


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )
    primary_instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("instruments.id", ondelete="restrict"),
        nullable=False,
        index=True,
    )
    strategy_type: Mapped[StrategyType] = mapped_column(
        SAEnum(
            StrategyType,
            name="strategy_type",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[PositionStatus] = mapped_column(
        SAEnum(
            PositionStatus,
            name="position_status",
            native_enum=False,
            values_callable=enum_values,
        ),
        nullable=False,
        default=PositionStatus.OPEN,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capital_used: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_risk_at_open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    max_reward_at_open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pnl_realized: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
