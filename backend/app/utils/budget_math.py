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
from typing import Iterable, List

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
