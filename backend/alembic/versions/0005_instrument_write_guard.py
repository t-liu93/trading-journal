"""Seed the shared instrument write coordination row.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO app_config (key, value) "
            "VALUES ('instrument_write_guard', '0')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM app_config WHERE key = 'instrument_write_guard'")
    )
