"""weddings: the suggested budget categories the couple removed (B71)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10 18:00:00.000000

One addition: an optional `declined_budget_defaults` column on weddings, a JSON
list of suggested category names (PD-013 call b) the couple removed, so the Budget
screen stops offering them. Blank means none, which is every existing wedding, so
there's no data step and nothing already entered changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.add_column('weddings',
                    sa.Column('declined_budget_defaults', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Forgets which suggestions were removed; the screen then offers them all again.
    safe.drop_column('weddings', 'declined_budget_defaults')
