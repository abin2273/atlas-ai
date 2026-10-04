"""Add embeddings to document chunks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b71d0c84e26"
down_revision: str | Sequence[str] | None = "8a3e6d291f47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
