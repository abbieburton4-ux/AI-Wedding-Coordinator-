"""checklist: a category per task, and the owner's Chicago tasks (B98, PD-021)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-13 12:00:00.000000

One addition: an optional `category` column on checklist_tasks. NULL shows as "Other".

The rest is a data step, run once by Alembic when the app starts, on both publish
paths (B60). For each wedding it:
1. gives every owner's-list, tradition and Wildman BT task its category, by its
   source_ref (PD-021 part 2). The AI planner's old tasks and the couple's own keep
   none, so they show as "Other" until the couple pick one;
2. adds the Chicago tasks C1-C12 (PD-021 part 3) to weddings whose checklist is already
   loaded, at the end of their stage, unticked, skipping any whose source_ref is already
   there or whose title is already on the list. A wedding that loads its checklist
   later gets them from the import instead;
3. gives task 1m-3 its Chicago wording (part 4) only while its title is still the
   original from the owner's file, compared by hash so that wording stays out of git.

No tick, note, stage, position or title the couple set is changed, and nothing is
deleted. Because Alembic runs this once, a Chicago task the couple delete afterwards
never comes back. The lists below are this release's copy, so the migration doesn't
change if app.utils.checklist does later.
"""
import datetime
import hashlib
import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from migrations import safe_ops as safe


# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRADITION_REFS = ('J1', 'J2', 'J3', 'J4', 'J5', 'J7', 'J8', 'J9', 'J10', 'J11', 'J12',
                  'J13', 'J17', 'J18', 'J20', 'J21', 'J23', 'J24')
CATEGORY_REFS = {
    'budget': ('12m-1', '12m-2', '12m-3', '11m-4', '6m-1', '3w-1', 'day-3',
               'V1', 'V2', 'V3', 'C11'),
    'venue_vendors': ('12m-4', '11m-1', '10m-2', '8m-1', '7m-1', '7m-5', '6m-2', '6m-4',
                      '2m-7', '3w-3', '2w-1', 'post-3', 'C1', 'C2', 'C3', 'C5', 'C9'),
    'guests': ('12m-5', '11m-2', '9m-4', '6m-5', '4m-2', '2m-2', '2m-3', '2m-4', '1m-4',
               '3w-2', '3w-4', '3w-5', '2w-2', '2-3d-3', 'C6', 'C8', 'C10'),
    'stationery': ('10m-3', '10m-4', '8m-2', '7m-2', '5m-3', '5m-4', '3m-6', '2m-5', '1m-5',
                   '1w-6', 'post-2'),
    'attire_beauty': ('11m-5', '10m-1', '7m-3', '7m-4', '5m-1', '5m-2', '4m-1', '3m-3',
                      '3m-5', '2m-1', '1m-1', '1w-4', '1w-5', '2-3d-5', '1d-3', 'post-1',
                      'C4', 'C7'),
    'ceremony': ('11m-3', '2m-6', '1m-2', '1m-3', '1w-2', '2-3d-2', '1d-2', 'post-4')
                + TRADITION_REFS,
    'events_honeymoon': ('10m-5', '9m-1', '9m-2', '9m-3', '6m-3', '4m-3', '4m-4', '3m-1',
                         '3m-2', '2m-8', '1m-7', '2w-3', '1w-1', '1w-7', '1d-4', 'post-5'),
    'day_of': ('3m-4', '1m-6', '1w-3', '2-3d-1', '2-3d-4', '1d-1', 'day-1', 'day-2',
               'day-4', 'day-5', 'day-6', 'day-7', 'day-8', 'C12'),
}

CHICAGO_TASKS = (
    ('C1', '12m', "Decide whether to hire a wedding planner or day-of coordinator. Wildman "
                  "BT offers a $1,500 day-of package, and the contract asks for a named "
                  "day-of contact either way"),
    ('C2', '10m', "Choose your caterer from Wildman BT's preferred list"),
    ('C3', '8m', "Reserve rentals (tables, chairs, linens, tableware) if the venue or caterer "
                 "doesn't supply them"),
    ('C4', '3m', "First fittings for the dress and suits (bring your wedding shoes and "
                 "undergarments)"),
    ('C5', '2m', "Give your DJ or band the music plan: processional, recessional, first dance, "
                 "must-play and do-not-play songs"),
    ('C6', '2m', "Keep track of meal choices and dietary needs from the RSVPs, for the caterer"),
    ('C7', '1m', "Hair and makeup trial"),
    ('C8', '1m', "Give Wildman BT your estimated guest count. Due Thu 23 Sep 2027"),
    ('C9', '1m', "Final walkthrough at Wildman BT with your planner and caterer"),
    ('C10', '1w', "Give Wildman BT your final guest count. Due Sat 16 Oct 2027"),
    ('C11', '1w', "Put vendor tips in labelled envelopes and choose who hands them out on the "
                  "day"),
    ('C12', '1w', "Pack a wedding-day emergency kit"),
)

LICENSE_REF = '1m-3'
LICENSE_ORIGINAL_SHA256 = 'a297a6b7d6d167229f7514ee3a5708a0f776ccc4817647c657f517d13221342b'
LICENSE_CHICAGO_TITLE = (
    "Get your marriage license from the Cook County Clerk. It's valid for 60 days and only "
    "for a ceremony in Chicago or suburban Cook County, so don't get it before late "
    "August 2027")


def upgrade() -> None:
    safe.add_column('checklist_tasks',
                    sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    apply_pd021(op.get_bind())


def _title_key(title: str) -> str:
    # The same comparison as app.utils.checklist.title_key, kept here so the migration
    # doesn't change if that function does.
    return re.sub(r'\s+', ' ', title or '').strip().rstrip('.').strip().casefold()


def apply_pd021(bind) -> None:
    """Categories, the Chicago tasks and the license wording; safe to run again."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    tasks = sa.table(
        'checklist_tasks', sa.column('id', sa.String()), sa.column('wedding_id', sa.String()),
        sa.column('stage', sa.String()), sa.column('title', sa.String()),
        sa.column('position', sa.Integer()), sa.column('done', sa.Boolean()),
        sa.column('source', sa.String()), sa.column('source_ref', sa.String()),
        sa.column('category', sa.String()),
        sa.column('created_at', sa.DateTime()), sa.column('updated_at', sa.DateTime()))
    weddings = sa.table('weddings', sa.column('id', sa.String()),
                        sa.column('checklist_imported_at', sa.DateTime()))

    # 1. Categories, only on list tasks that have none yet.
    for category, refs in CATEGORY_REFS.items():
        bind.execute(
            tasks.update()
            .where(tasks.c.source.in_(('owner_list', 'tradition')))
            .where(tasks.c.source_ref.in_(refs))
            .where(tasks.c.category.is_(None))
            .values(category=category))

    # 2. The Chicago tasks, for weddings whose checklist is loaded.
    loaded = bind.execute(
        sa.select(weddings.c.id).where(weddings.c.checklist_imported_at.isnot(None))
        .order_by(weddings.c.id)).scalars().all()
    category_by_ref = {ref: cat for cat, refs in CATEGORY_REFS.items() for ref in refs}
    for wedding_id in loaded:
        rows = bind.execute(
            sa.select(tasks.c.stage, tasks.c.title, tasks.c.position, tasks.c.source_ref)
            .where(tasks.c.wedding_id == wedding_id)).all()
        refs = {r.source_ref for r in rows if r.source_ref}
        titles = {_title_key(r.title) for r in rows}
        last = {}
        for r in rows:
            last[r.stage] = max(last.get(r.stage, 0), r.position or 0)
        new = []
        for ref, stage, title in CHICAGO_TASKS:
            if ref in refs or _title_key(title) in titles:
                continue
            last[stage] = last.get(stage, 0) + 1
            new.append(dict(
                id=str(uuid.uuid4()), wedding_id=wedding_id, stage=stage, title=title,
                position=last[stage], done=False, source='owner_list', source_ref=ref,
                category=category_by_ref[ref], created_at=now, updated_at=now))
        if new:
            bind.execute(tasks.insert(), new)

    # 3. The marriage-license task, only while it still has the original title.
    for task_id, title in bind.execute(
            sa.select(tasks.c.id, tasks.c.title)
            .where(tasks.c.source == 'owner_list', tasks.c.source_ref == LICENSE_REF)).all():
        if hashlib.sha256(_title_key(title).encode('utf-8')).hexdigest() \
                == LICENSE_ORIGINAL_SHA256:
            bind.execute(tasks.update().where(tasks.c.id == task_id)
                         .values(title=LICENSE_CHICAGO_TITLE, updated_at=now))


def downgrade() -> None:
    # Forgets every task's category. The Chicago tasks and the license wording stay,
    # since the couple may have ticked or edited them since. Upgrading again re-runs the
    # data step, which would bring back any Chicago task the couple deleted.
    safe.drop_column('checklist_tasks', 'category')
