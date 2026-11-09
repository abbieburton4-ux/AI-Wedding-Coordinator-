"""budget: expenses and payments that add up, and the Wildman BT entries (B65, PD-013)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-09 21:00:00.000000

Only additions: new columns on budget_costs and budget_payments, each optional or
with a default, plus one index, one foreign key and four new checks. No existing
column, constraint or check changes, so every expense and payment already entered
reads as before (archived off, not refundable, contract "none").

The Wildman BT expense is a data step, so it's added here, when the app starts, on
both publish paths (B60). It covers weddings that exist at upgrade time, skips any
wedding whose budget already has a Wildman BT expense, and marks nothing paid
(rule 4); the couple tick what they've paid.
"""
import datetime
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# From the Wildman BT draft contract the owner shared (docs/product/budget.md and
# wedding.md, updated 11/9/2026, not yet signed). Amounts are whole US cents.
WILDMAN_NAME = 'Wildman BT'
WILDMAN_PRICE_CENTS = 1_200_000
WILDMAN_NOTES = ('From the draft contract (updated 11/9/2026), not yet signed. '
                 'Paying by card adds 3%; paying by check doesn\'t.')
WILDMAN_PAYMENTS = (
    # (id suffix, kind, cents, due, refundable, notes)
    ('deposit', 'deposit', 600_000, datetime.date(2026, 11, 11), False,
     'Deposit, non-refundable.'),
    ('balance', 'payment', 600_000, datetime.date(2027, 9, 23), False,
     'Remaining balance.'),
    ('security', 'deposit', 200_000, datetime.date(2027, 9, 23), True,
     'Refundable security deposit, not part of the venue\'s cost. Returned within 30 '
     'days of the event, minus any damage, cleanup or overtime charges.'),
)
# An existing category with one of these names (ignoring case and spacing) is used;
# otherwise "Venue & Catering" is added, the name PD-013 step 3 gives the category.
VENUE_CATEGORY_KEYS = ('venue', 'venues', 'venue & catering', 'venue and catering')
NEW_CATEGORY_NAME = 'Venue & Catering'


def upgrade() -> None:
    cost_columns = (
        sa.Column('estimated_cents', sa.Integer(), nullable=True),
        sa.Column('final_cents', sa.Integer(), nullable=True),
        sa.Column('contract_status', sa.String(), nullable=False,
                  server_default=sa.text("'none'")),
        sa.Column('payment_method', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('link_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('couple_vendor_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for column in cost_columns:
        safe.add_column('budget_costs', column)
    safe.create_index('ix_budget_costs_couple_vendor_id', 'budget_costs',
                      ['couple_vendor_id'])
    safe.create_foreign_key('fk_budget_costs_couple_vendor_id_couple_vendors',
                            'budget_costs', 'couple_vendors', ['couple_vendor_id'], ['id'],
                            ondelete='SET NULL')
    safe.create_check_constraint('ck_budget_cost_estimated', 'budget_costs',
                                 'estimated_cents IS NULL OR estimated_cents >= 0')
    safe.create_check_constraint('ck_budget_cost_final', 'budget_costs',
                                 'final_cents IS NULL OR final_cents >= 0')
    safe.create_check_constraint('ck_budget_cost_contract', 'budget_costs',
                                 "contract_status IN ('none', 'sent', 'signed')")

    payment_columns = (
        sa.Column('paid_on', sa.Date(), nullable=True),
        sa.Column('method', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('link_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('refundable', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for column in payment_columns:
        safe.add_column('budget_payments', column)

    add_wildman_bt(op.get_bind())


def _key(name: str) -> str:
    # The same comparison as budget_split.category_key, kept here so the migration
    # doesn't change if that function does.
    return ' '.join((name or '').replace('_', ' ').lower().split())


def add_wildman_bt(bind) -> None:
    """The venue's expense and three unpaid payments, once per wedding (PD-013 c)."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    weddings = sa.table('weddings', sa.column('id', sa.String()))
    categories = sa.table(
        'budget_categories', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('name', sa.String()), sa.column('planned_cents', sa.Integer()),
        sa.column('created_at', sa.DateTime()), sa.column('updated_at', sa.DateTime()))
    costs = sa.table(
        'budget_costs', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('category_id', sa.String()), sa.column('vendor_name', sa.String()),
        sa.column('quoted_cents', sa.Integer()), sa.column('contract_status', sa.String()),
        sa.column('notes', sa.Text()), sa.column('couple_vendor_id', sa.String()),
        sa.column('archived', sa.Boolean()),
        sa.column('created_at', sa.DateTime()), sa.column('updated_at', sa.DateTime()))
    payments = sa.table(
        'budget_payments', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('cost_id', sa.String()), sa.column('kind', sa.String()),
        sa.column('amount_cents', sa.Integer()), sa.column('due_on', sa.Date()),
        sa.column('paid', sa.Boolean()), sa.column('notes', sa.Text()),
        sa.column('refundable', sa.Boolean()), sa.column('created_at', sa.DateTime()))
    vendors = sa.table(
        'couple_vendors', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('section', sa.String()), sa.column('name', sa.String()),
        sa.column('created_at', sa.DateTime()))

    for (wedding_id,) in bind.execute(sa.select(weddings.c.id).order_by(weddings.c.id)):
        existing = bind.execute(sa.select(costs.c.vendor_name).where(
            costs.c.wedding_id == wedding_id)).scalars().all()
        if any(_key(name) == _key(WILDMAN_NAME) for name in existing):
            continue

        rows = bind.execute(
            sa.select(categories.c.id, categories.c.name)
            .where(categories.c.wedding_id == wedding_id)
            .order_by(categories.c.created_at, categories.c.id)).all()
        category_id = next((cid for cid, name in rows if _key(name) in VENUE_CATEGORY_KEYS),
                           None)
        if category_id is None:
            category_id = str(uuid.uuid4())
            bind.execute(categories.insert().values(
                id=category_id, wedding_id=wedding_id, name=NEW_CATEGORY_NAME,
                planned_cents=None, created_at=now, updated_at=now))

        vendor_ids = [vid for vid, name in bind.execute(
            sa.select(vendors.c.id, vendors.c.name)
            .where(vendors.c.wedding_id == wedding_id, vendors.c.section == 'venue')
            .order_by(vendors.c.created_at, vendors.c.id)).all()
            if _key(name) == _key(WILDMAN_NAME)]

        cost_id = str(uuid.uuid4())
        # A quoted cost, not a final one, and contract "none": it isn't signed yet,
        # and only the couple change either (rule 4).
        bind.execute(costs.insert().values(
            id=cost_id, wedding_id=wedding_id, category_id=category_id,
            vendor_name=WILDMAN_NAME, quoted_cents=WILDMAN_PRICE_CENTS,
            contract_status='none', notes=WILDMAN_NOTES,
            couple_vendor_id=vendor_ids[0] if vendor_ids else None, archived=False,
            created_at=now, updated_at=now))
        bind.execute(payments.insert(), [
            dict(id=str(uuid.uuid4()), wedding_id=wedding_id, cost_id=cost_id, kind=kind,
                 amount_cents=cents, due_on=due, paid=False, notes=notes,
                 refundable=refundable, created_at=now)
            for _, kind, cents, due, refundable, notes in WILDMAN_PAYMENTS
        ])


def downgrade() -> None:
    # Forgets every estimate, final cost, contract status, note, link, vendor link,
    # archive mark, paid date, method, reference and refundable mark the couple
    # entered. The Wildman BT rows stay, and its refundable deposit would then count
    # as an ordinary payment. Never run this against real data.
    for column in ('refundable', 'link_url', 'notes', 'reference', 'method', 'paid_on'):
        safe.drop_column('budget_payments', column)
    safe.drop_constraint('ck_budget_cost_contract', 'budget_costs', 'check')
    safe.drop_constraint('ck_budget_cost_final', 'budget_costs', 'check')
    safe.drop_constraint('ck_budget_cost_estimated', 'budget_costs', 'check')
    safe.drop_constraint('fk_budget_costs_couple_vendor_id_couple_vendors', 'budget_costs',
                         'foreignkey')
    safe.drop_index('ix_budget_costs_couple_vendor_id', 'budget_costs')
    for column in ('archived', 'couple_vendor_id', 'link_url', 'notes', 'payment_method',
                   'contract_status', 'final_cents', 'estimated_cents'):
        safe.drop_column('budget_costs', column)
