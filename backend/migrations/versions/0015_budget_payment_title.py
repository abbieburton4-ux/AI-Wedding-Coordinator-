"""budget: an optional title on each payment (B102, PD-025)

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-18 12:00:00.000000

One addition: an optional `title` column on budget_payments. There's no data step:
every existing payment starts with no title and still shows as "Deposit" or "Payment",
and no amount, date or paid tick changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.add_column('budget_payments',
                    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    # Payments lose their titles and show as "Deposit"/"Payment" again; nothing else changes.
    safe.drop_column('budget_payments', 'title')
