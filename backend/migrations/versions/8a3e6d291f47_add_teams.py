"""Add organization teams and team memberships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a3e6d291f47"
down_revision: str | Sequence[str] | None = "6cf74d2a08b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp_default = (
        sa.text("CURRENT_TIMESTAMP")
        if op.get_context().dialect.name == "sqlite"
        else sa.text("now()")
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug"),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])
    op.create_table(
        "team_memberships",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("team_id", "user_id"),
    )
    op.create_index("ix_team_memberships_user_id", "team_memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_team_memberships_user_id", table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_index("ix_teams_organization_id", table_name="teams")
    op.drop_table("teams")
