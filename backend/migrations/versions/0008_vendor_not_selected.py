"""vendors: the couple can mark a vendor "Not selected" (B64)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-09 18:00:00.000000

One new column on couple_vendors, nothing else changed. It's a flag rather than a
fourth value in ck_couple_vendor_status, so Publish only adds a column; changing the
check would have meant dropping and re-adding it (B60). Every existing vendor starts
as not ruled out, so their statuses read exactly as before.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    safe.add_column('couple_vendors', sa.Column(
        'not_selected', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # Forgets which vendors the couple ruled out; each one goes back to the status it
    # had before, so one ruled out after booking shows as booked again. Never run this
    # against real data.
    safe.drop_column('couple_vendors', 'not_selected')
