"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe
${imports if imports else ""}

# Replit's Publish may already have made this migration's schema change in
# production, with alembic_version still behind (B60). Make every schema change
# through `safe.*` (same names and arguments as op.*), not op.* or batch_op.*:
# autogenerate's output below must be rewritten, and verify_migrations.py refuses
# raw calls. Data steps (op.execute) still run only here, after the schema change.
# No renames. Add a line for this revision to replit.md, "What Publish should show".

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
