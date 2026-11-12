"""budget: tips as their own expense lines (B79, PD-017)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12 18:00:00.000000

Only additions: two optional columns on budget_costs, `tip_for_cost_id` (the expense
a tip is for, with its index and a foreign key back to budget_costs) and
`tip_basis_points` (a percentage tip's rate). There's no data step: every existing
expense starts as a plain line, not a tip, and no amount, date or paid tick changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.add_column('budget_costs',
                    sa.Column('tip_for_cost_id', sqlmodel.sql.sqltypes.AutoString(),
                              nullable=True))
    safe.add_column('budget_costs', sa.Column('tip_basis_points', sa.Integer(), nullable=True))
    safe.create_index('ix_budget_costs_tip_for_cost_id', 'budget_costs', ['tip_for_cost_id'])
    safe.create_foreign_key('fk_budget_costs_tip_for_cost_id_budget_costs',
                            'budget_costs', 'budget_costs', ['tip_for_cost_id'], ['id'],
                            ondelete='SET NULL')


def downgrade() -> None:
    # Tips become plain lines; a percentage tip still following its expense's cost
    # loses its amount. Every other figure, payment and tick stays.
    safe.drop_constraint('fk_budget_costs_tip_for_cost_id_budget_costs', 'budget_costs',
                         'foreignkey')
    safe.drop_index('ix_budget_costs_tip_for_cost_id', 'budget_costs')
    safe.drop_column('budget_costs', 'tip_basis_points')
    safe.drop_column('budget_costs', 'tip_for_cost_id')
