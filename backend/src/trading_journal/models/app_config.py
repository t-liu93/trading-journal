"""``AppConfig`` — a generic key/value store for server-managed runtime config.

Unlike ``Settings`` (operator-supplied env vars), these values are generated and
owned by the app itself and must survive restarts. First use: ``cookie_secret``,
generated on first boot and reused thereafter so operators never supply it (see
``auth/secret.py``). Future global settings (default theme, market-data keys, …)
can be added as new keys without a schema change.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
