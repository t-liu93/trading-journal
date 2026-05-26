"""Add archived_at to trades for audit-friendly soft-delete (P9).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("trades", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_trades_archived_at"), ["archived_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("trades", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_trades_archived_at"))
        batch_op.drop_column("archived_at")
