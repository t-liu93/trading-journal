"""Immutable preview drafts for MCP journal entry."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from trading_journal.db import Base


class JournalEntryDraft(Base):
    __tablename__ = "journal_entry_drafts"
    __table_args__ = (
        Index(
            "uq_journal_entry_drafts_user_credential_request",
            "user_id",
            "credential_id",
            "request_id",
            unique=True,
        ),
        Index("ix_journal_entry_drafts_expiry", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
    credential_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("mcp_tokens.id", ondelete="cascade"), nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_input: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    preview: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    defaults: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
