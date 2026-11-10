"""The budget's figures, worked out whenever it's read (PD-004, PD-013 step 1).

Nothing here is stored and every sum is whole cents, so editing or removing an
expense or payment changes the figures straight away and nothing can drift.

The rules, in full:
- An expense's cost ("committed") is its final cost if set, else its quoted cost,
  else its estimate, else the payments scheduled on it so far (refundable ones left
  out), else 0. ``committed_basis`` says which one it came from.
- A refundable payment (a security deposit) is money the vendor holds and should
  return, not part of the cost. It's counted separately and never in "paid".
- Paid is the ticked, non-refundable payments. Still to pay is the cost minus paid,
  never below 0; paying more than the cost shows as overpaid instead, per expense,
  never netted against another expense.
- An expense's status is "overdue" when any payment on it (refundable or not) is
  unpaid and was due before today in Chicago; otherwise "paid" when it has a cost,
  every non-refundable payment is ticked and paid covers the cost; otherwise
  "partly_paid" when paid is above 0; otherwise "unpaid". Refundable deposits
  don't affect paid or partly paid, so the status never contradicts "Paid".
- Archived expenses keep their figures and status but are left out of every
  category and budget total, and out of the payments due.
"""
import datetime
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

CONTRACT_STATUSES = ("none", "sent", "signed")
EXPENSE_STATUSES = ("unpaid", "partly_paid", "paid", "overdue")

# Summed per category and for the whole budget, over expenses that aren't archived.
SUM_FIELDS = ("committed_cents", "paid_cents", "remaining_cents", "overpaid_cents",
              "refundable_cents", "refundable_paid_cents")


def committed(cost, payments: Iterable) -> tuple:
    """(cents, basis): final, quote or estimate if set, else the scheduled payments."""
    for cents, basis in ((cost.final_cents, "final"), (cost.quoted_cents, "quote"),
                         (cost.estimated_cents, "estimate")):
        if cents is not None:
            return cents, basis
    scheduled = sum(p.amount_cents for p in payments if not p.refundable)
    return (scheduled, "scheduled") if scheduled else (0, "none")


def basis_of(parts: Iterable[str]) -> str:
    """One basis for several expenses: theirs if they agree, else "mixed"."""
    kinds = {p for p in parts if p != "none"}
    if not kinds:
        return "none"
    return kinds.pop() if len(kinds) == 1 else "mixed"


def is_overdue(payment, today: datetime.date) -> bool:
    return not payment.paid and payment.due_on is not None and payment.due_on < today


@dataclass
class CostFigures:
    committed_cents: int
    committed_basis: str
    scheduled_cents: int
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
    # Scheduled non-refundable payments beyond the cost: the "payments add up to
    # more than the cost" warning. 0 when the cost is the scheduled payments.
    over_scheduled_cents: int
    refundable_cents: int
    refundable_paid_cents: int
    status: str
    # For each unpaid, non-refundable payment: how far over the cost paid would be
    # if it were ticked (0 when it wouldn't be). Drives the warning before ticking.
    would_overpay: dict = field(default_factory=dict)


def cost_figures(cost, payments: List, today: datetime.date) -> CostFigures:
    total, basis = committed(cost, payments)
    owed = [p for p in payments if not p.refundable]
    held = [p for p in payments if p.refundable]
    scheduled = sum(p.amount_cents for p in owed)
    paid = sum(p.amount_cents for p in owed if p.paid)

    # Paid and partly paid describe the cost, so a refundable deposit doesn't count
    # towards either (only towards overdue): the badge always agrees with "Paid".
    if any(is_overdue(p, today) for p in payments):
        status = "overdue"
    elif total > 0 and paid >= total and all(p.paid for p in owed):
        status = "paid"
    elif paid > 0:
        status = "partly_paid"
    else:
        status = "unpaid"

    return CostFigures(
        committed_cents=total, committed_basis=basis, scheduled_cents=scheduled,
        paid_cents=paid,
        remaining_cents=max(total - paid, 0),
        overpaid_cents=max(paid - total, 0),
        over_scheduled_cents=max(scheduled - total, 0),
        refundable_cents=sum(p.amount_cents for p in held),
        refundable_paid_cents=sum(p.amount_cents for p in held if p.paid),
        status=status,
        would_overpay={p.id: max(paid + p.amount_cents - total, 0)
                       for p in owed if not p.paid},
    )


def add_up(rows: Iterable) -> dict:
    """Sums SUM_FIELDS over figures (objects or dicts with those attributes)."""
    rows = list(rows)
    return {f: sum(getattr(r, f) for r in rows) for f in SUM_FIELDS}


def format_cents(cents: int) -> str:
    """"$12,500" or "$12,500.50", for text the app writes itself."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    rest = f".{cents % 100:02d}" if cents % 100 else ""
    return f"{sign}${cents // 100:,}{rest}"


# --- The dashboard (PD-013 step 2, B66) -----------------------------------------------
#
# Measured against a target (a category's target, or the couple's total):
# - "no_target" when there's no target (blank), so nothing can be over it;
# - "over" when committed is more than the target (a 0 target with anything on it);
# - "near_limit" when committed is at least NEAR_LIMIT_PCT of the target;
# - "within" otherwise, including a 0 target with nothing committed.
# Percentages are whole numbers worked out in integers; nothing here is stored.

NEAR_LIMIT_PCT = 90
TARGET_STATES = ("no_target", "within", "near_limit", "over")
# The contingency category is found by its name (case, spaces and underscores
# ignored), so it needs no database change and matches the default categories.
CONTINGENCY_NAME = "Contingency"


def target_state(target: Optional[int], committed_cents: int) -> str:
    if target is None:
        return "no_target"
    if committed_cents > target:
        return "over"
    if target > 0 and committed_cents * 100 >= target * NEAR_LIMIT_PCT:
        return "near_limit"
    return "within"


def pct_floor(part: int, whole: Optional[int]) -> Optional[int]:
    """Part of whole as a whole percent, rounded down so 100 means really all of it;
    None when there's nothing (or 0) to measure against."""
    if not whole:
        return None
    return part * 100 // whole


def pct_round(part: int, whole: Optional[int]) -> Optional[int]:
    """Part of whole as a whole percent, rounded half up; None without a whole."""
    if not whole:
        return None
    return (part * 200 + whole) // (whole * 2)


def target_figures(target: Optional[int], committed_cents: int,
                   total: Optional[int]) -> dict:
    """A category's figures against its target and against the couple's total."""
    has = target is not None
    return {
        "state": target_state(target, committed_cents),
        "share_pct": pct_round(target, total) if has else None,
        "target_left_cents": max(target - committed_cents, 0) if has else None,
        "over_target_cents": max(committed_cents - target, 0) if has else 0,
        "used_pct": pct_floor(committed_cents, target) if has else None,
    }


def dashboard_figures(total: Optional[int], planned_cents: int, committed_cents: int,
                      remaining_cents: int, states: Iterable[str]) -> dict:
    """The whole budget's figures for the dashboard cards and bars.

    ``total`` is the couple's overall budget (None when not set yet, never 0); the
    category targets add up to ``planned_cents``. "Paid toward the cost" is committed
    minus still to pay, so overpaying one vendor never makes the budget look further
    along than it is while another is still owed.
    """
    states = list(states)
    has = total is not None
    toward = committed_cents - remaining_cents
    return {
        "budget_state": target_state(total, committed_cents) if has else "not_set",
        "left_of_total_cents": max(total - committed_cents, 0) if has else None,
        "over_total_cents": max(committed_cents - total, 0) if has else None,
        "unallocated_cents": max(total - planned_cents, 0) if has else None,
        "over_allocated_cents": max(planned_cents - total, 0) if has else None,
        "allocated_pct": pct_floor(planned_cents, total) if has else None,
        "committed_pct": pct_floor(committed_cents, total) if has else None,
        "paid_toward_cost_cents": toward,
        "paid_pct": pct_floor(toward, committed_cents),
        "categories_over": sum(1 for s in states if s == "over"),
        "categories_near_limit": sum(1 for s in states if s == "near_limit"),
        "near_limit_pct": NEAR_LIMIT_PCT,
    }
