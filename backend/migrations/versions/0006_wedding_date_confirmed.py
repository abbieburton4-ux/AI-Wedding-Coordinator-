"""checklist: the couple's "This date is confirmed" switch (B48)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Every existing wedding starts as not confirmed; only the couple switch it on.
    # Adding a column is a plain ALTER TABLE on both SQLite and Postgres.
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'wedding_date_confirmed', sa.Boolean(), nullable=False, server_default=sa.false(),
        ))


def downgrade() -> None:
    # Loses only the switch's state; the date itself is kept. On SQLite, batch mode
    # copies the table, which is safe while nothing turns on PRAGMA foreign_keys
    # (see 0005).
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.drop_column('wedding_date_confirmed')
