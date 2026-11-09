"""The wedding's shared planning checklist (PD-007).

One list per wedding: when either partner ticks a task, everyone sees it. Anyone on
the access list can read it; only owners and editors can tick, add, rename, delete,
change the wedding date or mark it confirmed. Ticking a task changes nothing else: no
payment is marked paid and no booking confirmed (rule 4), and nothing here contacts
anyone (rule 1).
Due dates, "catch up" and "overdue" come from ``app.utils.checklist``.
"""
import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.v1.access import require_wedding_access
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import ChecklistTask, User, utcnow
from app.db.session import get_db
from app.utils import checklist as rules

router = APIRouter()

TITLE_MAX = 300
NOTES_MAX = 2000


# --- Request bodies -------------------------------------------------------------------

class DateIn(BaseModel):
    wedding_date: Optional[datetime.date] = None


class ConfirmedIn(BaseModel):
    confirmed: bool


class TaskIn(BaseModel):
    stage: str
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX)


class TaskPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=TITLE_MAX)
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX)


class DoneIn(BaseModel):
    done: bool


# --- Responses ------------------------------------------------------------------------

class TaskOut(BaseModel):
    id: str
    stage: str
    title: str
    notes: Optional[str]
    position: int
    done: bool
    done_at: Optional[datetime.datetime]
    done_by_name: Optional[str]
    # "catch_up" or "overdue" for an unfinished task; null otherwise.
    label: Optional[Literal["catch_up", "overdue"]]


class GroupOut(BaseModel):
    key: str
    label: str
    kind: Literal["catch_up", "stage"]
    stage_keys: List[str]
    due_on: Optional[datetime.date]
    # The stage this group's new tasks go into.
    add_to_stage: str
    current: bool
    done: int
    total: int
    tasks: List[TaskOut]


class ChecklistOut(BaseModel):
    wedding_date: Optional[datetime.date]
    date_set_on: Optional[datetime.date]
    # The couple's "This date is confirmed" switch (B48); off means provisional.
    date_confirmed: bool
    today: datetime.date
    done: int
    total: int
    overdue: int
    groups: List[GroupOut]


# --- Helpers --------------------------------------------------------------------------

def _today() -> datetime.date:
    # One place to read the date, so tests can fix it.
    return rules.wedding_today()


def _clean(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise HTTPException(status_code=422, detail="Please type the task")
    return text


def _clean_notes(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = text.strip()
    return text or None


async def _task(db: AsyncSession, task_id: str, wedding_id: str) -> ChecklistTask:
    row = (await db.exec(
        select(ChecklistTask).where(ChecklistTask.id == task_id,
                                    ChecklistTask.wedding_id == wedding_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="That task isn't on this checklist")
    return row


async def _names(db: AsyncSession, user_ids: set) -> dict:
    if not user_ids:
        return {}
    rows = (await db.exec(select(User).where(User.id.in_(sorted(user_ids))))).all()
    return {u.id: u.name for u in rows}


def _task_out(row: ChecklistTask, group, names: dict) -> TaskOut:
    return TaskOut(
        id=row.id, stage=row.stage, title=row.title, notes=row.notes, position=row.position,
        done=row.done, done_at=row.done_at if row.done else None,
        done_by_name=names.get(row.done_by_user_id) if row.done else None,
        label=rules.task_label(group, row.done),
    )


async def _checklist(db: AsyncSession, wedding) -> ChecklistOut:
    today = _today()
    tasks = (await db.exec(
        select(ChecklistTask).where(ChecklistTask.wedding_id == wedding.id)
        .order_by(ChecklistTask.position, ChecklistTask.created_at, ChecklistTask.id)
    )).all()
    names = await _names(db, {t.done_by_user_id for t in tasks if t.done and t.done_by_user_id})

    by_stage: dict = {}
    for t in tasks:
        # A task whose stage was dropped from the code still shows, in the first stage,
        # rather than vanishing.
        key = t.stage if t.stage in rules.STAGE_BY_KEY else rules.STAGE_KEYS[0]
        by_stage.setdefault(key, []).append(t)

    plans = rules.plan_groups(wedding.wedding_date, wedding.wedding_date_set_on, today)
    grouped = []
    for plan in plans:
        rows = [t for key in plan.stage_keys for t in by_stage.get(key, [])]
        grouped.append((plan, rows))
    undone = {plan.key: sum(1 for t in rows if not t.done) for plan, rows in grouped}
    current = set(rules.current_group_keys(plans, undone, today))

    groups = []
    for plan, rows in grouped:
        groups.append(GroupOut(
            key=plan.key, label=plan.label, kind=plan.kind, stage_keys=plan.stage_keys,
            due_on=plan.due_on, add_to_stage=plan.stage_keys[-1], current=plan.key in current,
            done=sum(1 for t in rows if t.done), total=len(rows),
            tasks=[_task_out(t, plan, names) for t in rows],
        ))
    return ChecklistOut(
        wedding_date=wedding.wedding_date, date_set_on=wedding.wedding_date_set_on,
        date_confirmed=wedding.wedding_date_confirmed, today=today,
        done=sum(g.done for g in groups), total=sum(g.total for g in groups),
        overdue=sum(1 for g in groups for t in g.tasks if t.label == "overdue"),
        groups=groups,
    )


async def _one(db: AsyncSession, wedding, row: ChecklistTask) -> TaskOut:
    """One task as the checklist would show it, with its label."""
    plans = rules.plan_groups(wedding.wedding_date, wedding.wedding_date_set_on,
                              _today())
    plan = next((p for p in plans if row.stage in p.stage_keys), plans[0])
    ids = {row.done_by_user_id} if row.done and row.done_by_user_id else set()
    return _task_out(row, plan, await _names(db, ids))


async def _editor(db: AsyncSession, wedding_id: str, user: User):
    return await require_wedding_access(db, wedding_id, user, "editor")


# --- Routes ---------------------------------------------------------------------------

@router.get("/{wedding_id}/checklist", response_model=ChecklistOut)
async def get_checklist(
    wedding_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """The whole checklist, grouped by stage, with due dates and progress."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
    return await _checklist(db, wedding)


@router.put("/{wedding_id}/checklist/date", response_model=ChecklistOut)
async def set_wedding_date(
    wedding_id: str, payload: DateIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Sets or clears the wedding date the due dates count back from.

    Records today as the day it was set, so stages already past move into "Catch up".
    Unlike PATCH /weddings/{id}, this doesn't send the plan back to the intake stage.
    The "date is confirmed" switch stays as it is; the couple change it themselves.
    """
    wedding = await _editor(db, wedding_id, current_user)
    today = _today()
    if payload.wedding_date is not None and payload.wedding_date < today:
        raise HTTPException(status_code=422, detail="Please pick a date that hasn't passed yet")
    if payload.wedding_date != wedding.wedding_date:
        wedding.wedding_date = payload.wedding_date
        wedding.wedding_date_set_on = today if payload.wedding_date else None
        db.add(wedding)
        await db.commit()
        await db.refresh(wedding)
    return await _checklist(db, wedding)


@router.put("/{wedding_id}/checklist/date-confirmed", response_model=ChecklistOut)
async def set_date_confirmed(
    wedding_id: str, payload: ConfirmedIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Switches "This date is confirmed" on or off (B48). Off brings back the
    "provisional" wording everywhere the date is shown."""
    wedding = await _editor(db, wedding_id, current_user)
    if payload.confirmed and wedding.wedding_date is None:
        raise HTTPException(status_code=422, detail="Set the wedding date first")
    if payload.confirmed != wedding.wedding_date_confirmed:
        wedding.wedding_date_confirmed = payload.confirmed
        db.add(wedding)
        await db.commit()
        await db.refresh(wedding)
    return await _checklist(db, wedding)


@router.post("/{wedding_id}/checklist/tasks", status_code=status.HTTP_201_CREATED,
             response_model=TaskOut)
async def add_task(
    wedding_id: str, payload: TaskIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Adds the couple's own task to the end of a stage."""
    wedding = await _editor(db, wedding_id, current_user)
    if payload.stage not in rules.STAGE_BY_KEY:
        raise HTTPException(status_code=422, detail="That stage isn't on the checklist")
    last = (await db.exec(
        select(func.max(ChecklistTask.position)).where(
            ChecklistTask.wedding_id == wedding_id, ChecklistTask.stage == payload.stage)
    )).first()
    row = ChecklistTask(
        wedding_id=wedding_id, stage=payload.stage, title=_clean(payload.title),
        notes=_clean_notes(payload.notes), position=(last or 0) + 1, source="couple",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _one(db, wedding, row)


@router.patch("/{wedding_id}/checklist/tasks/{task_id}", response_model=TaskOut)
async def edit_task(
    wedding_id: str, task_id: str, payload: TaskPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Renames a task or changes its notes."""
    wedding = await _editor(db, wedding_id, current_user)
    row = await _task(db, task_id, wedding_id)
    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates:
        row.title = _clean(updates["title"] or "")
    if "notes" in updates:
        row.notes = _clean_notes(updates["notes"])
    row.updated_at = utcnow()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _one(db, wedding, row)


@router.put("/{wedding_id}/checklist/tasks/{task_id}/done", response_model=TaskOut)
async def set_done(
    wedding_id: str, task_id: str, payload: DoneIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Ticks or unticks a task, recording who ticked it and when.

    Ticking an already-ticked task keeps the original record; unticking clears it.
    """
    wedding = await _editor(db, wedding_id, current_user)
    row = await _task(db, task_id, wedding_id)
    if payload.done != row.done:
        row.done = payload.done
        row.done_at = utcnow() if payload.done else None
        row.done_by_user_id = current_user.id if payload.done else None
        row.updated_at = utcnow()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return await _one(db, wedding, row)


@router.delete("/{wedding_id}/checklist/tasks/{task_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(
    wedding_id: str, task_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Deletes any task, whether the couple added it or it came from a list."""
    await _editor(db, wedding_id, current_user)
    row = await _task(db, task_id, wedding_id)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
