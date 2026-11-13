"""The budget as an Excel file with tabs (PD-019, B88), downloaded to the person's own
device.

Every figure is read from the budget overview (``budget._overview``), which works them
out on read in ``utils/budget_math.py``, so the file agrees with the Budget screen; its
labels come from ``utils/budget_export.py``. The two screen views that the browser groups
for itself, "Who paid" and the upcoming-payments groups, are grouped here by the same
rules as ``frontend/.../budget/figures.js`` (``whoPaid`` and ``groupOf``), from the
same overview rows; nothing is summed differently.

Money cells are real numbers in a US-dollar format, written as exact decimals from
whole cents (no float arithmetic). Dates are real dates. Every text cell is stored as
text, never as a formula, and one that looks like a formula also gets Excel's "quote
prefix", so it stays text even if someone edits it later. The file is .xlsx (no
macros), built in memory and returned; nothing is stored, logged or sent anywhere.
"""
import datetime
import io
import re
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.utils.budget_export import (
    BASIS_LABELS, BUDGET_LABELS, CONTRACT_LABELS, CURRENCY, FORMULA_STARTS, KIND_LABELS,
    STATUS_LABELS, TARGET_LABELS, payment_status,
)

MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

MONEY_FORMAT = '"$"#,##0.00'
DATE_FORMAT = "mmm d, yyyy"
DATETIME_FORMAT = "mmm d, yyyy h:mm AM/PM"
# Beyond the control characters openpyxl strips: what XML can't hold at all (lone
# surrogates and U+FFFE/U+FFFF). One left in would make the whole file unreadable.
NOT_XML_RE = re.compile("[\ud800-\udfff\ufffe\uffff]")
# Excel's limit for one cell's text.
MAX_CELL_TEXT = 32767

TIP_LABELS = {
    "amount": "Dollar amount", "following": "Percentage, follows the cost",
    "frozen": "Percentage, fixed when a payment was ticked paid",
    "waiting": "Percentage, waiting for a cost",
}
GROUP_LABELS = {
    "overdue": "Overdue", "week": "Due in the next 7 days", "month": "Due in 8 to 30 days",
    "later": "Later, or no due date yet",
}
GROUPS = ("overdue", "week", "month", "later")

BOLD = Font(bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")


class Money:
    """Whole cents, written as a dollar number."""
    __slots__ = ("cents",)

    def __init__(self, cents: Optional[int]):
        self.cents = cents


class Number:
    """A plain number (a count or a percentage)."""
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


# A column: (heading, width in characters, wraps long text).
Column = Tuple[str, int, bool]


def filename(today: datetime.date) -> str:
    return f"wedding-budget-{today.isoformat()}.xlsx"


def looks_like_formula(text: str) -> bool:
    return text.startswith(FORMULA_STARTS) or text.lstrip(" ").startswith(FORMULA_STARTS)


def dollars(cents: int) -> Decimal:
    """Whole cents as an exact dollar amount: 1200050 is 12000.50."""
    return Decimal(cents).scaleb(-2)


def percent_number(basis_points: Optional[int]) -> Optional[Decimal]:
    """Hundredths of a percent as a percentage number: 1850 is 18.5."""
    if basis_points is None:
        return None
    return Decimal(basis_points).scaleb(-2).normalize()


def _put(cell, value) -> None:
    if value is None:
        return
    if isinstance(value, Money):
        if value.cents is None:
            return
        cell.value = dollars(value.cents)
        cell.number_format = MONEY_FORMAT
    elif isinstance(value, Number):
        if value.value is None:
            return
        cell.value = value.value
    elif isinstance(value, datetime.datetime):
        cell.value = value
        cell.number_format = DATETIME_FORMAT
    elif isinstance(value, datetime.date):
        cell.value = value
        cell.number_format = DATE_FORMAT
    else:
        text = NOT_XML_RE.sub("", ILLEGAL_CHARACTERS_RE.sub("", str(value)))[:MAX_CELL_TEXT]
        cell.value = text
        # openpyxl reads a leading "=" as a formula; this cell is text, whatever it says.
        cell.data_type = "s"
        if looks_like_formula(text):
            cell.quotePrefix = True


def _sheet(wb: Workbook, title: str, columns: Sequence[Column], rows: List[list],
           footer: str, empty: Optional[str] = None):
    ws = wb.create_sheet(title)
    for i, (heading, width, _) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=i)
        _put(cell, heading)
        cell.font = BOLD
        cell.alignment = WRAP
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"
    if not rows and empty:
        _put(ws.cell(row=2, column=1), empty)
    for r, row in enumerate(rows, start=2):
        for i, value in enumerate(row, start=1):
            cell = ws.cell(row=r, column=i)
            _put(cell, value)
            cell.alignment = WRAP if columns[i - 1][2] else TOP
    ws.oddFooter.left.text = footer
    ws.evenFooter.left.text = footer
    ws.print_title_rows = "1:1"
    return ws


def _yes(value: bool) -> str:
    return "Yes" if value else "No"


def _box(cost) -> Optional[int]:
    """The "estimate or quote" box: the quote if there is one, else the estimate."""
    return cost.quoted_cents if cost.quoted_cents is not None else cost.estimated_cents


def group_of(due, today: datetime.date) -> str:
    """As the Budget screen groups an unpaid payment: overdue (the API's flag), due in
    the next 7 days (today included), in 8 to 30 days, or later (or no date)."""
    if due.overdue:
        return "overdue"
    if due.due_on is None:
        return "later"
    if due.due_on <= today + datetime.timedelta(days=7):
        return "week"
    if due.due_on <= today + datetime.timedelta(days=30):
        return "month"
    return "later"


def upcoming_groups(overview) -> dict:
    """The overview's unpaid payments (archived expenses already left out), grouped and
    soonest first; undated ones last."""
    groups = {g: [] for g in GROUPS}
    for due in overview.next_due:
        groups[group_of(due, overview.today)].append(due)
    for items in groups.values():
        items.sort(key=lambda d: (d.due_on is None, d.due_on or overview.today,
                                  d.vendor_name.casefold(), d.vendor_name))
    return groups


def who_paid(overview) -> List[dict]:
    """Per person on the "People who pay" list, in order: paid (ticked) and still to
    come, then a "Not set" row when any payment names nobody. Refundable deposits and
    archived expenses aren't counted; contributions (promises) never are."""
    rows = [{"id": p.id, "name": p.name, "paid": 0, "to_come": 0, "count": 0}
            for p in overview.payers]
    not_set = {"id": None, "name": "Not set", "paid": 0, "to_come": 0, "count": 0}
    by_id = {r["id"]: r for r in rows}
    for cat in overview.categories:
        for cost in cat.costs:
            if cost.archived:
                continue
            for p in cost.payments:
                if p.refundable:
                    continue
                row = by_id.get(p.payer_id) if p.payer_id else None
                row = row or not_set
                row["paid" if p.paid else "to_come"] += p.amount_cents
                row["count"] += 1
    return rows + [not_set] if not_set["count"] else rows


def build_xlsx(overview, vendors: dict, now: datetime.datetime,
               include_archived: bool = False, include_contacts: bool = False) -> bytes:
    """The whole workbook as bytes.

    ``overview`` is the budget overview; ``vendors`` maps a Vendors-page id to its row,
    for the website and, only when ``include_contacts``, the contact name, email and
    phone. ``now`` is the Chicago date and time of the snapshot (naive). Archived
    expenses are never in a total; ``include_archived`` only lists them.
    """
    t, d = overview.totals, overview.dashboard
    taken = f"{now:%B} {now.day}, {now.year} at {now.hour % 12 or 12}:{now:%M %p}"
    footer = f"Snapshot taken {taken} Chicago time. It doesn't update; download again " \
             "for the latest figures."

    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = "Wedding budget"
    wb.properties.lastModifiedBy = "Wedding budget"
    wb.properties.title = "Wedding budget"

    # The shown expenses, in the screen's order.
    shown = [(cat, cost) for cat in overview.categories for cost in cat.costs
             if include_archived or not cost.archived]
    groups = upcoming_groups(overview)
    contingency = next((c for c in overview.categories
                        if c.id == d.contingency_id), None) if d.contingency_id else None

    summary = [
        ["Snapshot taken (Chicago time)", now],
        ["About this file", "A snapshot of the Budget page. It doesn't update; download "
                            "it again for the latest figures."],
        ["Currency", CURRENCY],
        ["Total budget", Money(t.total_cents) if t.total_cents is not None else "Not set"],
        ["Category targets added up", Money(t.planned_cents)],
        ["Committed", Money(t.committed_cents)],
        ["Committed based on", BASIS_LABELS.get(t.committed_basis, t.committed_basis)],
        ["Paid", Money(t.paid_cents)],
        ["Still to pay", Money(t.remaining_cents)],
        ["Overpaid", Money(t.overpaid_cents)],
        ["Budget status", BUDGET_LABELS.get(d.budget_state, d.budget_state)],
        ["Left of total budget", Money(d.left_of_total_cents)
         if d.left_of_total_cents is not None else "Total not set"],
        ["Over total budget", Money(d.over_total_cents)
         if d.over_total_cents is not None else "Total not set"],
        ["Not yet given to a category", Money(d.unallocated_cents)],
        ["Contingency target", (Money(contingency.planned_cents)
                                if contingency.planned_cents is not None else "Not set")
         if contingency else "No Contingency category"],
        ["Contingency committed", Money(contingency.committed_cents) if contingency
         else "No Contingency category"],
        ["Contingency left", Money(contingency.target_left_cents) if contingency
         and contingency.target_left_cents is not None else None],
        ["Refundable deposits (not part of the cost)", Money(t.refundable_cents)],
        ["Refundable deposits paid", Money(t.refundable_paid_cents)],
        ["Tips (already part of committed)", Money(d.tips_cents)],
        ["Tips counted", Number(d.tip_count)],
        ["Contributions (promised)", Money(t.contributions_cents)],
        ["Categories over target", Number(d.categories_over)],
        ["Expenses counted", Number(d.expense_count)],
        ["Payments overdue", Number(d.overdue_count)],
        ["Payments coming up", Number(d.upcoming_count)],
    ]
    for g in GROUPS:
        summary.append([f"{GROUP_LABELS[g]} (total)",
                        Money(sum(x.amount_cents for x in groups[g]))])
    summary += [
        ["Archived expenses", "Listed, but not in any total" if include_archived
         else "Not included"],
        ["Vendor contact details", "Included" if include_contacts else "Not included"],
    ]
    _sheet(wb, "Summary", [("Item", 44, False), ("Value", 60, True)], summary, footer)

    categories = [[
        cat.name, Money(cat.planned_cents), Number(cat.share_pct),
        Money(cat.committed_cents), Money(cat.paid_cents), Money(cat.remaining_cents),
        Money(cat.overpaid_cents), Money(cat.target_left_cents),
        Money(cat.over_target_cents), TARGET_LABELS.get(cat.state, cat.state),
        Number(cat.expense_count),
    ] for cat in overview.categories]
    _sheet(wb, "Categories", [
        ("Category", 28, True), ("Target", 14, False), ("Share of total budget (%)", 12, False),
        ("Committed", 14, False), ("Paid", 14, False), ("Still to pay", 14, False),
        ("Overpaid", 12, False), ("Left of target", 14, False), ("Over target", 14, False),
        ("Status", 16, False), ("Expenses", 10, False),
    ], categories, footer, empty="No categories yet.")

    contact_cols: List[Column] = ([("Vendor contact", 20, True), ("Vendor email", 26, True),
                                   ("Vendor phone", 16, False)] if include_contacts else [])
    expenses = []
    for cat, cost in shown:
        v = vendors.get(cost.vendor.id) if cost.vendor else None
        contacts = ([v.contact_name if v else None, v.email if v else None,
                     v.phone if v else None] if include_contacts else [])
        expenses.append([
            cat.name, cost.vendor_name, Money(_box(cost)), Money(cost.final_cents),
            Money(cost.committed_cents),
            BASIS_LABELS.get(cost.committed_basis, cost.committed_basis),
            Money(cost.paid_cents), Money(cost.remaining_cents),
            Money(cost.refundable_cents),
            CONTRACT_LABELS.get(cost.contract_status, cost.contract_status),
            STATUS_LABELS.get(cost.status, cost.status), cost.next_due_on,
            v.name if v else None, v.website if v else None, *contacts,
            cost.tip_for_name, Number(percent_number(cost.tip_basis_points)),
            cost.payment_method, cost.notes, cost.link_url, _yes(cost.archived),
        ])
    _sheet(wb, "Expenses", [
        ("Category", 22, True), ("Expense", 28, True), ("Estimate or quote", 14, False),
        ("Actual", 14, False), ("Counted cost", 14, False), ("Cost based on", 16, False),
        ("Paid", 14, False), ("Still to pay", 14, False),
        ("Refundable deposits", 14, False), ("Contract", 10, False), ("Status", 12, False),
        ("Next due", 14, False), ("Linked vendor", 24, True), ("Vendor website", 30, True),
        *contact_cols, ("Tip for", 24, True), ("Tip (%)", 9, False),
        ("Payment method", 16, True), ("Comments", 44, True), ("Link", 36, True),
        ("Archived", 10, False),
    ], expenses, footer, empty="No expenses yet.")

    payments = [[
        cost.vendor_name, cat.name, KIND_LABELS.get(p.kind, p.kind), Money(p.amount_cents),
        p.due_on, _yes(p.paid), p.paid_on, p.payer_name or "Not set", p.method,
        p.reference, _yes(p.refundable), payment_status(p), p.notes, p.link_url,
    ] for cat, cost in shown for p in cost.payments]
    _sheet(wb, "Payments", [
        ("Expense", 28, True), ("Category", 22, True), ("Type", 10, False),
        ("Amount", 14, False), ("Due", 14, False), ("Paid", 8, False),
        ("Date paid", 14, False), ("Who paid", 20, True), ("How it was paid", 18, True),
        ("Reference", 18, True), ("Refundable", 11, False), ("Status", 10, False),
        ("Notes", 44, True), ("Link", 36, True),
    ], payments, footer, empty="No payments yet.")

    upcoming = [[
        GROUP_LABELS[g], due.due_on, due.vendor_name, due.category_name,
        KIND_LABELS.get(due.kind, due.kind), Money(due.amount_cents), _yes(due.refundable),
    ] for g in GROUPS for due in groups[g]]
    _sheet(wb, "Upcoming", [
        ("When", 26, False), ("Due", 14, False), ("Expense", 28, True),
        ("Category", 22, True), ("Type", 10, False), ("Amount", 14, False),
        ("Refundable", 11, False),
    ], upcoming, footer, empty="Nothing left to pay.")

    payers = [[r["name"], Money(r["paid"]), Money(r["to_come"]),
               Money(r["paid"] + r["to_come"]), Number(r["count"])]
              for r in who_paid(overview)]
    _sheet(wb, "Who paid", [
        ("Who", 26, True), ("Paid", 14, False), ("Still to come", 14, False),
        ("Together", 14, False), ("Payments", 10, False),
    ], payers, footer, empty="Nobody added to the People who pay list yet.")

    tips = [[
        cost.vendor_name, cost.tip_for_name, cat.name,
        TIP_LABELS.get(cost.tip_state, cost.tip_state),
        Number(percent_number(cost.tip_basis_points)), Money(cost.committed_cents),
        Money(cost.paid_cents), Money(cost.remaining_cents), _yes(cost.archived),
    ] for cat, cost in shown if cost.tip_state is not None]
    _sheet(wb, "Tips", [
        ("Tip", 28, True), ("For which expense", 28, True), ("Category", 22, True),
        ("Worked out as", 26, True), ("Percentage (%)", 12, False), ("Amount", 14, False),
        ("Paid", 14, False), ("Still to pay", 14, False), ("Archived", 10, False),
    ], tips, footer, empty="No tips added yet.")

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

