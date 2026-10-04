"""Add document processing lifecycle and version history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6cf74d2a08b1"
down_revision: str | Sequence[str] | None = "45b6c1a7d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version_group_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("raw_content", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "processing_status",
            sa.String(length=20),
            server_default="READY",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE documents SET version_group_id = id WHERE version_group_id IS NULL"
    )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "version_group_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
        batch_op.alter_column(
            "version_number",
            existing_type=sa.Integer(),
            server_default=None,
        )
        batch_op.alter_column(
            "processing_status",
            existing_type=sa.String(length=20),
            server_default=None,
        )
        batch_op.create_unique_constraint(
            "uq_documents_version_group_number",
            ["version_group_id", "version_number"],
        )
        batch_op.create_index("ix_documents_version_group_id", ["version_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_index("ix_documents_version_group_id")
        batch_op.drop_constraint("uq_documents_version_group_number", type_="unique")
        batch_op.drop_column("processing_error")
        batch_op.drop_column("processing_status")
        batch_op.drop_column("raw_content")
        batch_op.drop_column("version_number")
        batch_op.drop_column("version_group_id")
