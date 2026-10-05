"""Add users table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd053d9ee1eb9'
down_revision: str | Sequence[str] | None = '69edeb326f62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp_default = (
        sa.text('CURRENT_TIMESTAMP')
        if op.get_context().dialect.name == 'sqlite'
        else sa.text('now()')
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
