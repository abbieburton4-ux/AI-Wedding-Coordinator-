"""The planning checklist's stages, due dates, and "catch up" and "overdue" rules (PD-007).

Due dates are never stored: each stage's date is the wedding date moved by the stage's
offset, worked out whenever the checklist is read, so changing the date moves them all.

The rule for past stages, in full:
- ``anchor`` is the day the wedding date was last set or changed. It's recorded
  whenever a date is set (intake, the date control, the profile, the import, and the
  0004 migration for weddings that already had one), so "today if unknown" is only a
  fallback for rows written some other way.
- A stage whose due date is before the anchor was already past when the date was
  chosen. All such stages are shown together as one "Catch up" group, due on the date
  of the first stage still ahead on the anchor day. Their unfinished tasks are
  labelled "catch up", never "overdue".
- Any other stage whose due date is before today has passed since the date was set;
  its unfinished tasks are labelled "overdue".
- With no wedding date there are no dates, no catch up and no overdue.
"""
import calendar
import datetime
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

# The wedding is in Chicago (docs/product/wedding.md), so "today" for due dates, "catch
# up" and "overdue" is the date there, not the server's.
WEDDING_TZ = ZoneInfo("America/Chicago")


def wedding_today() -> datetime.date:
    return datetime.datetime.now(WEDDING_TZ).date()


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    months: int = 0
    weeks: int = 0
    days: int = 0


# The owner's stages, in their order (PD-007). Negative offsets are before the wedding.
STAGES = (
    Stage("12m", "12 Months Before", months=-12),
    Stage("11m", "11 Months Before", months=-11),
    Stage("10m", "10 Months Before", months=-10),
    Stage("9m", "9 Months Before", months=-9),
    Stage("8m", "8 Months Before", months=-8),
    Stage("7m", "7 Months Before", months=-7),
    Stage("6m", "6 Months Before", months=-6),
    Stage("5m", "5 Months Before", months=-5),
    Stage("4m", "4 Months Before", months=-4),
    Stage("3m", "3 Months Before", months=-3),
    Stage("2m", "2 Months Before", months=-2),
    Stage("1m", "1 Month Before", months=-1),
    Stage("3w", "3 Weeks Before", weeks=-3),
    Stage("2w", "2 Weeks Before", weeks=-2),
    Stage("1w", "1 Week Before", weeks=-1),
    Stage("2-3d", "2–3 Days Before", days=-3),
    Stage("1d", "The Day Before", days=-1),
    Stage("day", "Your Wedding Day!", days=0),
    Stage("post", "Post-Wedding", weeks=2),
)
STAGE_KEYS = tuple(s.key for s in STAGES)
STAGE_BY_KEY = {s.key: s for s in STAGES}

# The Jewish traditions the couple approved (PD-007 call (d)), in the product lane's
# wording (docs/product/checklist-list.md, part 2). J2 replaces the owner's list's
# "find the person to officiate" task, item 11m-3.
TRADITIONS = (
    ("J1", "12m", "Check your date with your rabbi or officiant against Shabbat and the Jewish holidays"),
    ("J2", "11m", "Find your rabbi or officiant, and ask what they need from you (for example a "
                  "meeting before the wedding, or rules about who can be a witness)"),
    ("J3", "10m", "Decide which ceremony traditions you're including (circling, the seven "
                  "blessings, breaking the glass)"),
    ("J4", "8m", "Choose and order your ketubah (marriage contract): text, artist and wording"),
    ("J5", "8m", "Decide on your chuppah (canopy): the venue's, rented, made by your florist, "
                 "or a family tallit"),
    ("J7", "5m", "Choose your ketubah witnesses"),
    ("J8", "5m", "Check with your rabbi about the rings (some traditions use a plain band with "
                 "no stones for the ceremony)"),
    ("J9", "4m", "Choose who will read or sing the seven blessings (sheva brachot)"),
    ("J10", "4m", "If the chuppah is held by hand, choose four people to hold the poles"),
    ("J11", "3m", "Order kippot (yarmulkes) for guests"),
    ("J12", "3m", "Write a short ceremony program that explains the traditions for guests who "
                  "don't know them"),
    ("J13", "2m", "Tell your band or DJ about the hora, and ask the venue for sturdy chairs for "
                  "the lift"),
    ("J17", "1m", "Get the glass to break, and a pouch for it if you want to keep the pieces"),
    ("J18", "1m", "Get a kiddush cup and the wine for the blessings"),
    ("J20", "1w", "Agree the processional order with your rabbi (in many Jewish weddings both "
                  "sets of parents walk each of you down)"),
    ("J21", "1d", "Bring the ketubah, the glass, the kiddush cup and the wine to the venue"),
    ("J23", "day", "Sign the ketubah with your rabbi and witnesses before the ceremony"),
    ("J24", "post", "Frame the ketubah, and turn the broken glass into a keepsake if you want one"),
)
# The owner's-list item that J2 takes the place of.
REPLACED_BY_J2 = "11m-3"

CATCH_UP_KEY = "catch_up"


def add_months(d: datetime.date, months: int) -> datetime.date:
    """Calendar months, keeping the day where it exists and otherwise using the month's
    last day (31 Aug minus 6 months is 28 or 29 Feb)."""
    month_index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def stage_due(wedding_date: datetime.date, stage: Stage) -> datetime.date:
    return add_months(wedding_date, stage.months) + datetime.timedelta(
        weeks=stage.weeks, days=stage.days
    )


def title_key(title: str) -> str:
    """How two task titles are compared for duplicates: case, spacing and a trailing
    full stop don't count."""
    return re.sub(r"\s+", " ", title).strip().rstrip(".").strip().casefold()


def nearest_stage(wedding_date: datetime.date, due: datetime.date) -> Stage:
    """The stage whose due date is closest to ``due``; the earlier one on a tie."""
    return min(STAGES, key=lambda s: (abs((stage_due(wedding_date, s) - due).days),
                                      STAGE_KEYS.index(s.key)))


@dataclass
class GroupPlan:
    key: str
    label: str
    stage_keys: List[str]
    due_on: Optional[datetime.date]
    kind: str  # "catch_up" or "stage"
    past: bool  # the due date is before today (never set for catch up)


def plan_groups(
    wedding_date: Optional[datetime.date],
    date_set_on: Optional[datetime.date],
    today: datetime.date,
) -> List[GroupPlan]:
    """The checklist's groups in order: "Catch up" first if any stage was already past
    when the date was set, then every other stage. See the module docstring."""
    if wedding_date is None:
        return [GroupPlan(s.key, s.label, [s.key], None, "stage", False) for s in STAGES]

    anchor = date_set_on or today
    dues = {s.key: stage_due(wedding_date, s) for s in STAGES}
    behind = [s for s in STAGES if dues[s.key] < anchor]
    ahead = [s for s in STAGES if dues[s.key] >= anchor]

    groups: List[GroupPlan] = []
    if behind:
        catch_up_due = dues[ahead[0].key] if ahead else None
        groups.append(GroupPlan(CATCH_UP_KEY, "Catch up", [s.key for s in behind],
                                catch_up_due, "catch_up", False))
    for s in ahead:
        groups.append(GroupPlan(s.key, s.label, [s.key], dues[s.key], "stage",
                                dues[s.key] < today))
    return groups


def task_label(group: GroupPlan, done: bool) -> Optional[str]:
    """ "catch_up" or "overdue" for an unfinished task, by its group; otherwise None."""
    if done:
        return None
    if group.kind == "catch_up":
        return "catch_up"
    if group.past:
        return "overdue"
    return None


def current_group_keys(groups: List[GroupPlan], undone_by_group: dict,
                       today: datetime.date) -> List[str]:
    """Which groups open by default: the next stage still ahead, plus "Catch up" while
    it has unfinished tasks. With no date, the first stage with unfinished tasks."""
    keys: List[str] = []
    if groups and groups[0].due_on is None and groups[0].kind == "stage":
        first = next((g for g in groups if undone_by_group.get(g.key)), None)
        return [first.key] if first else []
    for g in groups:
        if g.kind == "catch_up" and undone_by_group.get(g.key):
            keys.append(g.key)
    upcoming = next((g for g in groups if g.kind == "stage" and g.due_on is not None
                     and g.due_on >= today), None)
    if upcoming:
        keys.append(upcoming.key)
    return keys


def validate_stage_keys(keys: Iterable[str]) -> List[str]:
    """Stage keys that aren't known, for import checks."""
    return [k for k in keys if k not in STAGE_BY_KEY]
