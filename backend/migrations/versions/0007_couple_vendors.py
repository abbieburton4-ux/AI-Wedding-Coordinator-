"""vendors: the couple's own vendors in each section, and Wildman BT in Venue (B62)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-09 13:06:17.703161

Two new tables, nothing else changed. Publish may create them first (B60); the
Wildman BT row is a data step, so it's added here, when the app starts, on both
paths. It covers weddings that exist at upgrade time; a wedding created later, or a
local `create_all` database, starts with an empty Venue section.
"""
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The venue the owner named for this wedding (PD-012, wedding.md). "contacted", not
# "booked": the contract isn't signed, and only the couple change the status.
WILDMAN_NAME = 'Wildman BT'
WILDMAN_WEBSITE = 'https://www.wildmanbt.com/'


def upgrade() -> None:
    safe.create_table(
        'couple_vendors',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('wedding_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('section', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('website', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('contact_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "section IN ('venue', 'food_drink', 'flowers_decoration', 'photo_video', "
            "'entertainment', 'hair_makeup', 'transportation')",
            name='ck_couple_vendor_section'),
        sa.CheckConstraint("status IN ('looking', 'contacted', 'booked')",
                           name='ck_couple_vendor_status'),
        sa.ForeignKeyConstraint(['wedding_id'], ['weddings.id'],
                                name='fk_couple_vendors_wedding_id_weddings',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_couple_vendors'),
    )
    safe.create_index('ix_couple_vendors_wedding_id', 'couple_vendors', ['wedding_id'])

    safe.create_table(
        'couple_vendor_quotes',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('vendor_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('total_cents', sa.Integer(), nullable=True),
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('line_items', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('total_cents IS NULL OR total_cents >= 0',
                           name='ck_couple_vendor_quote_total'),
        sa.ForeignKeyConstraint(['vendor_id'], ['couple_vendors.id'],
                                name='fk_couple_vendor_quotes_vendor_id_couple_vendors',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_couple_vendor_quotes'),
    )
    safe.create_index('ix_couple_vendor_quotes_vendor_id', 'couple_vendor_quotes',
                      ['vendor_id'])

    # Data step: Wildman BT in Venue for the wedding, unless its Venue section already
    # has it. The app plans one wedding (PD-001), so this is that wedding's row. It
    # runs once, through Alembic, so a row the couple delete later stays deleted.
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    weddings = sa.table('weddings', sa.column('id', sa.String()))
    vendors = sa.table(
        'couple_vendors', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('section', sa.String()), sa.column('name', sa.String()),
        sa.column('website', sa.String()), sa.column('status', sa.String()),
        sa.column('notes', sa.Text()), sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )
    already = (sa.select(vendors.c.id)
               .where(vendors.c.wedding_id == weddings.c.id,
                      vendors.c.section == 'venue', vendors.c.name == WILDMAN_NAME)
               .exists())
    rows = sa.select(
        (sa.literal('wildman-bt-') + weddings.c.id).label('id'),
        weddings.c.id,
        sa.literal('venue'),
        sa.literal(WILDMAN_NAME),
        sa.literal(WILDMAN_WEBSITE),
        sa.literal('contacted'),
        sa.literal('Your chosen venue.'),
        sa.literal(now, sa.DateTime()),
        sa.literal(now, sa.DateTime()),
    ).where(~already)
    op.execute(vendors.insert().from_select(
        ['id', 'wedding_id', 'section', 'name', 'website', 'status', 'notes',
         'created_at', 'updated_at'], rows))


def downgrade() -> None:
    # Drops every vendor the couple added and every reply the AI read. Never run this
    # against real data.
    safe.drop_index('ix_couple_vendor_quotes_vendor_id', 'couple_vendor_quotes')
    safe.drop_table('couple_vendor_quotes')
    safe.drop_index('ix_couple_vendors_wedding_id', 'couple_vendors')
    safe.drop_table('couple_vendors')
