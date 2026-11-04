"""Store immutable MCP journal entry previews.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "journal_entry_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("normalized_input", sa.JSON(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("defaults", sa.JSON(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["mcp_tokens.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_journal_entry_drafts_user_credential_request",
        "journal_entry_drafts",
        ["user_id", "credential_id", "request_id"],
        unique=True,
    )
    op.create_index("ix_journal_entry_drafts_expiry", "journal_entry_drafts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_journal_entry_drafts_expiry", table_name="journal_entry_drafts")
    op.drop_index(
        "uq_journal_entry_drafts_user_credential_request", table_name="journal_entry_drafts"
    )
    op.drop_table("journal_entry_drafts")
