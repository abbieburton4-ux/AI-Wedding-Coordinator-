"""setup form: the intake budget can be left blank (PD-009)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only relaxes NOT NULL: every existing value is kept. On Postgres this is a plain
    # ALTER COLUMN; on SQLite, batch mode copies the table (foreign keys are off there
    # during migrations, so no child rows are touched).
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.alter_column('budget_total', existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    # A blank budget has no honest number to put back, so refuse rather than invent one.
    bind = op.get_bind()
    blank = bind.execute(
        sa.text("SELECT COUNT(*) FROM weddings WHERE budget_total IS NULL")
    ).scalar()
    if blank:
        raise RuntimeError(
            f"{blank} wedding(s) have no intake budget; set one before downgrading below 0005."
        )
    with op.batch_alter_table('weddings', schema=None) as batch_op:
        batch_op.alter_column('budget_total', existing_type=sa.Float(), nullable=False)
