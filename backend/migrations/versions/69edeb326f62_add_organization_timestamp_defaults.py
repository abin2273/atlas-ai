"""Add database-side defaults to organization timestamps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '69edeb326f62'
down_revision: str | Sequence[str] | None = '77a979508d86'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_default() -> sa.TextClause:
    if op.get_context().dialect.name == 'sqlite':
        return sa.text('CURRENT_TIMESTAMP')
    return sa.text('now()')


def upgrade() -> None:
    default = _timestamp_default()
    if op.get_context().dialect.name == 'sqlite':
        with op.batch_alter_table('organizations') as batch_op:
            batch_op.alter_column(
                'created_at',
                existing_type=sa.DateTime(timezone=True),
                server_default=default,
            )
            batch_op.alter_column(
                'updated_at',
                existing_type=sa.DateTime(timezone=True),
                server_default=default,
            )
        return

    op.alter_column('organizations', 'created_at', server_default=default)
    op.alter_column('organizations', 'updated_at', server_default=default)


def downgrade() -> None:
    if op.get_context().dialect.name == 'sqlite':
        with op.batch_alter_table('organizations') as batch_op:
            batch_op.alter_column(
                'updated_at',
                existing_type=sa.DateTime(timezone=True),
                server_default=None,
            )
            batch_op.alter_column(
                'created_at',
                existing_type=sa.DateTime(timezone=True),
                server_default=None,
            )
        return

    op.alter_column('organizations', 'updated_at', server_default=None)
    op.alter_column('organizations', 'created_at', server_default=None)
