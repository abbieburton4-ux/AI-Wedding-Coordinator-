"""budget: the couple's own order for categories (B67, PD-013 step 3)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-10 12:00:00.000000

One addition: an optional whole-number `sort_order` column on budget_categories.
Nothing else changes; the default categories and their suggestions live in code
(`utils/budget_defaults.py`), not in the database, and the brief's groups are the
categories themselves, so there's no group table.

The data step then numbers each wedding's categories that have no number yet,
after any that do, in the order they were added, which is the order the screen
showed before. Running it again finds nothing to number, and it never renumbers a
category the couple have placed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.add_column('budget_categories',
                    sa.Column('sort_order', sa.Integer(), nullable=True))
    number_categories(op.get_bind())


def number_categories(bind) -> None:
    """Gives each wedding's unnumbered categories the order they were added in."""
    categories = sa.table(
        'budget_categories', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('sort_order', sa.Integer()), sa.column('created_at', sa.DateTime()))
    rows = bind.execute(
        sa.select(categories.c.id, categories.c.wedding_id, categories.c.sort_order)
        .order_by(categories.c.wedding_id, categories.c.created_at, categories.c.id)).all()
    next_number: dict = {}
    for _, wid, order in rows:
        if order is not None:
            next_number[wid] = max(next_number.get(wid, 0), order + 1)
    for cid, wid, order in rows:
        if order is None:
            position = next_number.get(wid, 0)
            bind.execute(categories.update().where(categories.c.id == cid)
                         .values(sort_order=position))
            next_number[wid] = position + 1


def downgrade() -> None:
    # Forgets the couple's order; categories then show in the order they were added.
    safe.drop_column('budget_categories', 'sort_order')
