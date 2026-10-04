"""Add organization memberships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '3d6c2e2905a7'
down_revision: str | Sequence[str] | None = 'd053d9ee1eb9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp_default = (
        sa.text('CURRENT_TIMESTAMP')
        if op.get_context().dialect.name == 'sqlite'
        else sa.text('now()')
    )
    op.create_table(
        'organization_memberships',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column(
            'role',
            sa.Enum('OWNER', 'ADMIN', 'MEMBER', 'VIEWER', name='membershiprole'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'organization_id'),
    )


def downgrade() -> None:
    op.drop_table('organization_memberships')
