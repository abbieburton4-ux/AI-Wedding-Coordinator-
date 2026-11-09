"""The one-off checklist import (PD-007), used by ``manage_checklist.py``.

In one transaction it:
1. optionally sets the wedding date (the owner's choice, never a default);
2. loads the owner's list from their own file, kept outside git (call (e));
3. adds the approved Jewish traditions, J2 taking the place of item 11m-3, and the
   Wildman BT contract's payment tasks V1-V3 (PD-011), whose dates are in their wording;
4. merges the AI planner's old timeline rows: each goes into the stage nearest its
   due date, unless its title matches a task already on the list, in which case its
   tick and notes move onto that task;
5. reads the checklist back and checks every timeline row is on it, then deletes them.

The caller commits only if nothing raised. A dry run does the same work on the live
database and rolls it back; it isn't a copy, so take a backup before ``--apply``
(RUNBOOK, "Loading the owner's checklist"). The app's "Load my checklist" step
(PD-011) runs the same code from the Checklist screen.

The file's wording goes only into the checklist rows: never into logs, the decision log
or the AI. Refusal messages name stages and positions, never a task's text.
"""
import datetime
import json
from dataclasses import dataclass, field
from typing import List, Optional

from sqlmodel import Session, select

from app.db.models import ChecklistTask, TimelineItem, Wedding, utcnow
from app.utils import checklist as rules

TITLE_MAX = 300
# The owner's file is about 10 kB; anything far bigger isn't her checklist.
FILE_MAX_CHARS = 200_000


class ImportRefused(Exception):
    """The import can't run safely; nothing has been written."""


@dataclass
class ImportReport:
    owner_tasks: int = 0
    tradition_tasks: int = 0
    venue_tasks: int = 0
    ai_added: List[str] = field(default_factory=list)
    ai_skipped: List[str] = field(default_factory=list)
    timeline_rows_removed: int = 0
    wedding_date: Optional[datetime.date] = None


def read_owner_list(path: str) -> list:
    """The stages from the owner's file on disk; see ``parse_owner_list``."""
    with open(path, encoding="utf-8") as f:
        return parse_owner_list(f.read())


def parse_owner_list(text: str) -> list:
    """The stages from the owner's file: a JSON list, or the first ```json block of a
    Markdown file. Checks each stage matches the app's stages, in the same order."""
    if len(text) > FILE_MAX_CHARS:
        raise ImportRefused("The file is too long to be the checklist")
    try:
        data = json.loads(_json_block(text))
    except json.JSONDecodeError as e:
        raise ImportRefused(f"The file's checklist isn't valid JSON: {e}")
    except RecursionError:
        raise ImportRefused("The file's checklist is nested too deeply to be the checklist")
    if not isinstance(data, list):
        raise ImportRefused("The file's checklist should be a list of stages")

    keys = [s.get("id") if isinstance(s, dict) else None for s in data]
    if keys != list(rules.STAGE_KEYS):
        # Names the first stage that differs by position, never what the file says.
        n = next((i for i, (a, b) in enumerate(zip(keys, rules.STAGE_KEYS)) if a != b),
                 min(len(keys), len(rules.STAGE_KEYS)))
        expected = rules.STAGES[n].label if n < len(rules.STAGES) else "the end of the list"
        raise ImportRefused(
            f"The file has {len(keys)} stages and the app has {len(rules.STAGE_KEYS)}; "
            f"they differ from stage {n + 1}, which should be {expected}")
    for stage, raw in zip(rules.STAGES, data):
        offset = raw.get("offset") or {}
        if not isinstance(offset, dict):
            raise ImportRefused(f"Stage {stage.key}'s offset should be months, weeks or days")
        expected = {k: v for k, v in (("months", stage.months), ("weeks", stage.weeks),
                                      ("days", stage.days)) if v}
        got = {k: v for k, v in offset.items() if v}
        if got != expected:
            raise ImportRefused(f"Stage {stage.key}'s offset isn't {expected or 0}")
        items = raw.get("items")
        if not isinstance(items, list) or not all(isinstance(i, str) and i.strip()
                                                  for i in items):
            raise ImportRefused(f"Stage {stage.key}'s items should be a list of task names")
        for item in items:
            if len(" ".join(item.split())) > TITLE_MAX:
                raise ImportRefused(f"A task in stage {stage.key} is over {TITLE_MAX} characters")
    return data


def _json_block(text: str) -> str:
    """The first ```json block of a Markdown file, or the whole text. Found with plain
    string search: a regex here backtracked for minutes on a fence with no end."""
    start = text.find("```json")
    if start < 0:
        return text
    body_start = text.find("\n", start)
    end = text.find("```", body_start + 1) if body_start >= 0 else -1
    if end < 0:
        return text
    return text[body_start + 1:end]


def _clean(title: str) -> str:
    return " ".join(title.split())[:TITLE_MAX]


def import_checklist(
    session: Session,
    wedding: Wedding,
    owner_list: list,
    wedding_date: Optional[datetime.date] = None,
    today: Optional[datetime.date] = None,
) -> ImportReport:
    today = today or rules.wedding_today()
    if wedding.checklist_imported_at is not None:
        raise ImportRefused(
            f"This wedding's checklist was already imported on "
            f"{wedding.checklist_imported_at:%d %b %Y}; nothing was changed")

    if wedding_date is not None:
        if wedding_date < today:
            raise ImportRefused("The wedding date has already passed")
        if wedding_date != wedding.wedding_date:
            wedding.wedding_date = wedding_date
            wedding.wedding_date_set_on = today
    if wedding.wedding_date is not None and wedding.wedding_date_set_on is None:
        # Without a "set on" day, stages that pass from now on would never show as
        # overdue; today is the first day the checklist counts from.
        wedding.wedding_date_set_on = today
    session.add(wedding)

    existing = session.exec(
        select(ChecklistTask).where(ChecklistTask.wedding_id == wedding.id)
    ).all()
    refs = {t.source_ref for t in existing if t.source_ref}
    by_title = {}
    for t in existing:
        by_title.setdefault(rules.title_key(t.title), t)
    next_position = {}
    for t in existing:
        next_position[t.stage] = max(next_position.get(t.stage, 0), t.position)

    report = ImportReport(wedding_date=wedding.wedding_date)

    def add(stage: str, title: str, source: str, ref: str, notes: Optional[str] = None,
            done: bool = False) -> bool:
        if ref in refs:
            return False
        next_position[stage] = next_position.get(stage, 0) + 1
        task = ChecklistTask(
            wedding_id=wedding.id, stage=stage, title=_clean(title), notes=notes,
            position=next_position[stage], source=source, source_ref=ref, done=done,
        )
        session.add(task)
        refs.add(ref)
        by_title.setdefault(rules.title_key(title), task)
        return True

    traditions = {}
    for ref, stage, title in rules.TRADITIONS:
        traditions.setdefault(stage, []).append((ref, title))
    venue = {}
    for ref, stage, title in rules.VENUE_TASKS:
        venue.setdefault(stage, []).append((ref, title))

    for stage, raw in zip(rules.STAGES, owner_list):
        stage_traditions = list(traditions.get(stage.key, []))
        for n, title in enumerate(raw["items"], start=1):
            ref = f"{stage.key}-{n}"
            if ref == rules.REPLACED_BY_J2:
                if "officiat" not in title.lower():
                    raise ImportRefused(
                        f"Item {ref} was expected to be about finding the officiant, which "
                        "the J2 tradition task replaces; the file's order may have changed")
                j2 = next(t for t in stage_traditions if t[0] == "J2")
                stage_traditions.remove(j2)
                report.tradition_tasks += add(stage.key, j2[1], "tradition", j2[0])
                continue
            report.owner_tasks += add(stage.key, title, "owner_list", ref)
        for ref, title in stage_traditions:
            report.tradition_tasks += add(stage.key, title, "tradition", ref)
        # The owner asked for these (PD-011), so they count as hers, not as traditions.
        for ref, title in venue.get(stage.key, []):
            report.venue_tasks += add(stage.key, title, "owner_list", ref)

    timeline = session.exec(
        select(TimelineItem).where(TimelineItem.wedding_id == wedding.id)
        .order_by(TimelineItem.due_at, TimelineItem.id)
    ).all()
    if timeline and wedding.wedding_date is None:
        raise ImportRefused(
            "The wedding has AI timeline tasks to merge, which need a wedding date to "
            "place them; set the wedding date first")

    for item in timeline:
        if f"ti:{item.id}" in refs:
            continue
        notes = (item.description or "").strip() or None
        match = by_title.get(rules.title_key(item.title))
        if match is not None:
            # Same task already on the list: keep the AI row's tick and notes on it.
            # The timeline never recorded when or by whom a row was done, so done_at
            # stays empty rather than guessed.
            carried = []
            if item.status == "done" and not match.done:
                match.done = True
                carried.append("ticked")
            if notes and not (match.notes or "").strip():
                match.notes = notes
                carried.append("notes copied")
            if carried:
                match.updated_at = utcnow()
                session.add(match)
            extra = f" ({', '.join(carried)})" if carried else ""
            report.ai_skipped.append(f"{_clean(item.title)} = {match.title}{extra}")
            continue
        stage = rules.nearest_stage(wedding.wedding_date, item.due_at)
        add(stage.key, item.title, "ai_timeline", f"ti:{item.id}", notes=notes,
            done=item.status == "done")
        report.ai_added.append(f"{item.title} -> {stage.label}")

    session.flush()
    _check_timeline_accounted_for(session, wedding.id, timeline)

    for item in timeline:
        session.delete(item)
    report.timeline_rows_removed = len(timeline)

    wedding.checklist_imported_at = utcnow()
    session.add(wedding)
    session.flush()
    return report


def _check_timeline_accounted_for(session: Session, wedding_id: str, timeline: list) -> None:
    """Before anything is deleted, read the checklist back from the database and check
    every timeline row is on it: merged as its own task with the same title, or matched
    by title to a task that's at least as done. Anything else refuses the import."""
    rows = session.exec(
        select(ChecklistTask.source_ref, ChecklistTask.title, ChecklistTask.done)
        .where(ChecklistTask.wedding_id == wedding_id)
    ).all()
    by_ref = {ref: (title, done) for ref, title, done in rows if ref}
    done_by_title = {}
    for _, title, done in rows:
        key = rules.title_key(title)
        done_by_title[key] = done_by_title.get(key, False) or done

    current = session.exec(
        select(TimelineItem.id).where(TimelineItem.wedding_id == wedding_id)
    ).all()
    if sorted(current) != sorted(i.id for i in timeline):
        raise ImportRefused("The timeline changed during the import; nothing was deleted")

    problems = []
    for item in timeline:
        was_done = item.status == "done"
        merged = by_ref.get(f"ti:{item.id}")
        if merged is not None:
            title, done = merged
            if title != _clean(item.title) or (was_done and not done):
                problems.append(item.id)
            continue
        key = rules.title_key(item.title)
        if key not in done_by_title or (was_done and not done_by_title[key]):
            problems.append(item.id)
    if problems:
        raise ImportRefused(
            f"{len(problems)} timeline rows aren't safely on the checklist; nothing was "
            "deleted")
