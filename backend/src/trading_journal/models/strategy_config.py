"""``StrategyConfig`` — per-user, per-strategy config rows (data-model.md §4.7)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base
from trading_journal.models._enums import StrategyType, enum_values


class StrategyConfig(Base):
    __tablename__ = "strategy_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "strategy_type", name="uq_strategy_configs_user_strategy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
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
    max_exposure: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    exposure_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
