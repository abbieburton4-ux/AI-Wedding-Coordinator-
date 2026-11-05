"""The one-off checklist import (PD-007), used by ``manage_checklist.py``.

In one transaction it:
1. optionally sets the wedding date (the owner's choice, never a default);
2. loads the owner's list from their own file, kept outside git (call (e));
3. adds the approved Jewish traditions, J2 taking the place of item 11m-3;
4. merges the AI planner's old timeline rows: each goes into the stage nearest its
   due date, unless its title matches a task already on the list;
5. checks every timeline row is accounted for, then deletes them.

The caller commits only if nothing raised; a dry run rolls the same work back.
"""
import datetime
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlmodel import Session, select

from app.db.models import ChecklistTask, TimelineItem, Wedding, utcnow
from app.utils import checklist as rules

TITLE_MAX = 300


class ImportRefused(Exception):
    """The import can't run safely; nothing has been written."""


@dataclass
class ImportReport:
    owner_tasks: int = 0
    tradition_tasks: int = 0
    ai_added: List[str] = field(default_factory=list)
    ai_skipped: List[str] = field(default_factory=list)
    timeline_rows_removed: int = 0
    wedding_date: Optional[datetime.date] = None


def read_owner_list(path: str) -> list:
    """The stages from the owner's file: a JSON list, or the first ```json block of a
    Markdown file. Checks each stage matches the app's stages, in the same order."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    block = re.search(r"```json\s*\n(.*?)```", text, re.S)
    try:
        data = json.loads(block.group(1) if block else text)
    except json.JSONDecodeError as e:
        raise ImportRefused(f"The file's checklist isn't valid JSON: {e}")
    if not isinstance(data, list):
        raise ImportRefused("The file's checklist should be a list of stages")

    keys = [s.get("id") if isinstance(s, dict) else None for s in data]
    if keys != list(rules.STAGE_KEYS):
        raise ImportRefused(
            f"The file's stages {keys} don't match the app's {list(rules.STAGE_KEYS)}")
    for stage, raw in zip(rules.STAGES, data):
        offset = raw.get("offset") or {}
        expected = {k: v for k, v in (("months", stage.months), ("weeks", stage.weeks),
                                      ("days", stage.days)) if v}
        got = {k: v for k, v in offset.items() if v}
        if got != expected:
            raise ImportRefused(f"Stage {stage.key}'s offset {offset} isn't {expected or 0}")
        items = raw.get("items")
        if not isinstance(items, list) or not all(isinstance(i, str) and i.strip()
                                                  for i in items):
            raise ImportRefused(f"Stage {stage.key}'s items should be a list of task names")
        for item in items:
            if len(" ".join(item.split())) > TITLE_MAX:
                raise ImportRefused(f"A task in stage {stage.key} is over {TITLE_MAX} characters")
    return data


def _clean(title: str) -> str:
    return " ".join(title.split())[:TITLE_MAX]


def import_checklist(
    session: Session,
    wedding: Wedding,
    owner_list: list,
    wedding_date: Optional[datetime.date] = None,
    today: Optional[datetime.date] = None,
) -> ImportReport:
    today = today or datetime.date.today()
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
            session.add(wedding)

    existing = session.exec(
        select(ChecklistTask).where(ChecklistTask.wedding_id == wedding.id)
    ).all()
    refs = {t.source_ref for t in existing if t.source_ref}
    known_titles = {rules.title_key(t.title) for t in existing}
    next_position = {}
    for t in existing:
        next_position[t.stage] = max(next_position.get(t.stage, 0), t.position)

    report = ImportReport(wedding_date=wedding.wedding_date)

    def add(stage: str, title: str, source: str, ref: str, notes: Optional[str] = None,
            done: bool = False) -> bool:
        if ref in refs:
            return False
        next_position[stage] = next_position.get(stage, 0) + 1
        session.add(ChecklistTask(
            wedding_id=wedding.id, stage=stage, title=_clean(title), notes=notes,
            position=next_position[stage], source=source, source_ref=ref, done=done,
        ))
        refs.add(ref)
        known_titles.add(rules.title_key(title))
        return True

    traditions = {}
    for ref, stage, title in rules.TRADITIONS:
        traditions.setdefault(stage, []).append((ref, title))

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

    timeline = session.exec(
        select(TimelineItem).where(TimelineItem.wedding_id == wedding.id)
        .order_by(TimelineItem.due_at, TimelineItem.id)
    ).all()
    if timeline and wedding.wedding_date is None:
        raise ImportRefused(
            "The wedding has AI timeline tasks to merge, which need a wedding date to "
            "place them; pass --wedding-date")

    skipped_ids = set()
    for item in timeline:
        if f"ti:{item.id}" in refs:
            continue
        if rules.title_key(item.title) in known_titles:
            skipped_ids.add(item.id)
            report.ai_skipped.append(item.title)
            continue
        stage = rules.nearest_stage(wedding.wedding_date, item.due_at)
        notes = (item.description or "").strip() or None
        add(stage.key, item.title, "ai_timeline", f"ti:{item.id}", notes=notes,
            done=item.status == "done")
        report.ai_added.append(f"{item.title} -> {stage.label}")

    session.flush()

    # Before deleting anything, check each timeline row is now on the checklist or was
    # skipped as a duplicate.
    merged = set(session.exec(
        select(ChecklistTask.source_ref).where(
            ChecklistTask.wedding_id == wedding.id, ChecklistTask.source == "ai_timeline")
    ).all())
    missing = [i.id for i in timeline
               if f"ti:{i.id}" not in merged and i.id not in skipped_ids]
    if missing:
        raise ImportRefused(f"{len(missing)} timeline rows weren't merged; nothing was deleted")

    for item in timeline:
        session.delete(item)
    report.timeline_rows_removed = len(timeline)

    wedding.checklist_imported_at = utcnow()
    session.add(wedding)
    session.flush()
    return report
