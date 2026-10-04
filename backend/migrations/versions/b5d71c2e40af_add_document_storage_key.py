"""Add external document storage keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d71c2e40af"
down_revision: str | Sequence[str] | None = "a4ce92f0017d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("storage_key", sa.String(length=512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "storage_key")
