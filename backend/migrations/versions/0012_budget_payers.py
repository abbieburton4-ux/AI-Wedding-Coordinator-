"""budget: the "People who pay" list and who paid each payment (B76, PD-016)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12 12:00:00.000000

Only additions: a new `budget_payers` table, and an optional `payer_id` column on
budget_payments with its index and foreign key. There's no data step. The list
starts empty, because the couple type the names in the app (PD-016 call a), and
every existing payment's payer starts blank for them to fill in (call b). No amount,
date or paid tick changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.create_table(
        'budget_payers',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('wedding_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['wedding_id'], ['weddings.id'],
                                name='fk_budget_payers_wedding_id_weddings',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_budget_payers'),
    )
    safe.create_index('ix_budget_payers_wedding_id', 'budget_payers', ['wedding_id'])

    safe.add_column('budget_payments',
                    sa.Column('payer_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    safe.create_index('ix_budget_payments_payer_id', 'budget_payments', ['payer_id'])
    safe.create_foreign_key('fk_budget_payments_payer_id_budget_payers',
                            'budget_payments', 'budget_payers', ['payer_id'], ['id'],
                            ondelete='SET NULL')


def downgrade() -> None:
    # Forgets who paid each payment and the list of names; amounts and ticks stay.
    safe.drop_constraint('fk_budget_payments_payer_id_budget_payers', 'budget_payments',
                         'foreignkey')
    safe.drop_index('ix_budget_payments_payer_id', 'budget_payments')
    safe.drop_column('budget_payments', 'payer_id')
    safe.drop_index('ix_budget_payers_wedding_id', 'budget_payers')
    safe.drop_table('budget_payers')
