"""``TradePlan`` — event stream of plan revisions per Position (data-model.md §4.6)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"
    __table_args__ = (
        UniqueConstraint("position_id", "revision_no", name="uq_trade_plans_position_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("positions.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_entry: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    planned_stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    planned_take_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_rr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
