"""Add extracted document metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4ce92f0017d"
down_revision: str | Sequence[str] | None = "9b71d0c84e26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "extracted_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "extracted_metadata")
