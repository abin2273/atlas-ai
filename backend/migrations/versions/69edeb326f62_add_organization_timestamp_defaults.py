"""add organization timestamp defaults

Revision ID: 69edeb326f62
Revises: 77a979508d86
Create Date: 2026-09-17 16:07:20.676007

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "69edeb326f62"
down_revision: str | Sequence[str] | None = "77a979508d86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add database-side defaults to organization timestamps."""
    op.alter_column(
        "organizations",
        "created_at",
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "organizations",
        "updated_at",
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    """Remove database-side defaults from organization timestamps."""
    op.alter_column(
        "organizations",
        "updated_at",
        server_default=None,
    )
    op.alter_column(
        "organizations",
        "created_at",
        server_default=None,
    )
