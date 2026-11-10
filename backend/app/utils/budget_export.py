"""The budget as one CSV file the person downloads to their own device (PD-013 step 5).

Every figure comes from the budget overview, which works them out on read
(``utils/budget_math.py``), so the file always agrees with the Budget screen. Nothing
here is stored, logged or sent anywhere.

The file is a single CSV with five sections, one after another: Summary, Categories,
Expenses, Payments and Upcoming. The first column always names the section, and each
section starts with its own header row, so the file opens straight in Google Sheets or
Excel and can be filtered by section.

Amounts are US dollars written plainly ("12000.00"); the column headers say "(USD)".
Any text cell that a spreadsheet could read as a formula is prefixed with an
apostrophe, so a name typed as "=HYPERLINK(...)" stays text.
"""
import csv
import datetime
import io
from typing import Iterable, List, Optional

CURRENCY = "USD"

STATUS_LABELS = {
    "unpaid": "Unpaid", "partly_paid": "Partly paid", "paid": "Paid", "overdue": "Overdue",
}
TARGET_LABELS = {
    "no_target": "No target", "within": "Within target", "near_limit": "Near limit",
    "over": "Over target",
}
BUDGET_LABELS = {
    "not_set": "Total not set", "within": "Within budget", "near_limit": "Near limit",
    "over": "Over budget",
}
BASIS_LABELS = {
    "none": "Nothing yet", "final": "Final cost", "quote": "Quote", "estimate": "Estimate",
    "scheduled": "Payments scheduled", "mixed": "Mixed",
}
CONTRACT_LABELS = {"none": "None", "sent": "Sent", "signed": "Signed"}
KIND_LABELS = {"deposit": "Deposit", "payment": "Payment"}

# What a spreadsheet may treat as the start of a formula: OWASP's list, plus the
# full-width forms some keyboards type, which some spreadsheets read the same way.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n",
                  "\uff1d", "\uff0b", "\uff0d", "\uff20")


def safe_cell(value) -> str:
    """A cell as text, with an apostrophe in front of anything that could run as a
    formula when the file is opened."""
    if value is None:
        return ""
    text = str(value)
    # Leading spaces are checked past too: some spreadsheets skip them first.
    if text.startswith(FORMULA_STARTS) or text.lstrip(" ").startswith(FORMULA_STARTS):
        return "'" + text
    return text


def dollars(cents: Optional[int]) -> str:
    """Whole cents as plain dollars ("12000.00"); blank for none. Integer maths only."""
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def _day(value: Optional[datetime.date]) -> str:
    return value.isoformat() if value else ""


def _yes(value: bool) -> str:
    return "Yes" if value else "No"


def filename(today: datetime.date) -> str:
    return f"wedding-budget-{today.isoformat()}.csv"


def payment_status(payment) -> str:
    if payment.paid:
        return "Paid"
    return "Overdue" if payment.overdue else "Unpaid"


def build_csv(overview, vendors: dict, include_archived: bool = False,
              include_contacts: bool = False) -> str:
    """The whole export as text.

    ``overview`` is the budget overview (``budget._overview``); ``vendors`` maps a
    Vendors-page id to its row, for the website and, only when ``include_contacts``,
    the contact name, email and phone. Archived expenses are always left out of the
    totals, as on the Budget screen; ``include_archived`` only lists them.
    """
    rows: List[list] = []
    t, d = overview.totals, overview.dashboard

    rows.append(["Section", "Item", "Value"])
    summary = [
        ("Exported on (Chicago date)", _day(overview.today)),
        ("Currency", CURRENCY),
        ("Total budget (USD)", dollars(t.total_cents) if t.total_cents is not None
         else "Not set"),
        ("Category targets added up (USD)", dollars(t.planned_cents)),
        ("Committed (USD)", dollars(t.committed_cents)),
        ("Committed based on", BASIS_LABELS.get(t.committed_basis, t.committed_basis)),
        ("Paid (USD)", dollars(t.paid_cents)),
        ("Still to pay (USD)", dollars(t.remaining_cents)),
        ("Overpaid (USD)", dollars(t.overpaid_cents)),
        ("Left of total budget (USD)", dollars(d.left_of_total_cents)),
        ("Over total budget (USD)", dollars(d.over_total_cents)),
        ("Not yet given to a category (USD)", dollars(d.unallocated_cents)),
        ("Refundable deposits (USD, not part of the cost)", dollars(t.refundable_cents)),
        ("Refundable deposits paid (USD)", dollars(t.refundable_paid_cents)),
        ("Contributions (USD)", dollars(t.contributions_cents)),
        ("Budget status", BUDGET_LABELS.get(d.budget_state, d.budget_state)),
        ("Categories over target", d.categories_over),
        ("Expenses counted", d.expense_count),
        ("Payments overdue", d.overdue_count),
        ("Payments coming up", d.upcoming_count),
        ("Archived expenses", "Listed, but not in any total" if include_archived
         else "Not included"),
        ("Vendor contact details", "Included" if include_contacts else "Not included"),
    ]
    rows += [["Summary", item, value] for item, value in summary]
    rows.append([])

    rows.append(["Section", "Category", "Target (USD)", "Share of total budget (%)",
                 "Committed (USD)", "Paid (USD)", "Still to pay (USD)", "Overpaid (USD)",
                 "Left of target (USD)", "Over target (USD)", "Status", "Expenses"])
    for cat in overview.categories:
        rows.append([
            "Categories", cat.name, dollars(cat.planned_cents),
            "" if cat.share_pct is None else cat.share_pct,
            dollars(cat.committed_cents), dollars(cat.paid_cents),
            dollars(cat.remaining_cents), dollars(cat.overpaid_cents),
            dollars(cat.target_left_cents), dollars(cat.over_target_cents),
            TARGET_LABELS.get(cat.state, cat.state), cat.expense_count,
        ])
    rows.append([])

    contact_heads = ["Vendor contact", "Vendor email", "Vendor phone"] if include_contacts else []
    rows.append(["Section", "Expense", "Category", "Linked vendor", "Vendor website",
                 *contact_heads, "Estimated (USD)", "Quoted (USD)", "Final (USD)",
                 "Cost (USD)", "Cost based on", "Paid (USD)", "Still to pay (USD)",
                 "Overpaid (USD)", "Refundable deposits (USD)", "Status", "Next due",
                 "Contract", "Payment method", "Link", "Notes", "Archived"])
    shown = []
    for cat in overview.categories:
        for cost in cat.costs:
            if cost.archived and not include_archived:
                continue
            shown.append((cat, cost))
            v = vendors.get(cost.vendor.id) if cost.vendor else None
            contacts = ([v.contact_name if v else None, v.email if v else None,
                         v.phone if v else None] if include_contacts else [])
            rows.append([
                "Expenses", cost.vendor_name, cat.name, v.name if v else None,
                v.website if v else None, *contacts,
                dollars(cost.estimated_cents), dollars(cost.quoted_cents),
                dollars(cost.final_cents), dollars(cost.committed_cents),
                BASIS_LABELS.get(cost.committed_basis, cost.committed_basis),
                dollars(cost.paid_cents), dollars(cost.remaining_cents),
                dollars(cost.overpaid_cents), dollars(cost.refundable_cents),
                STATUS_LABELS.get(cost.status, cost.status), _day(cost.next_due_on),
                CONTRACT_LABELS.get(cost.contract_status, cost.contract_status),
                cost.payment_method, cost.link_url, cost.notes, _yes(cost.archived),
            ])
    rows.append([])

    rows.append(["Section", "Expense", "Category", "Type", "Amount (USD)", "Due",
                 "Paid", "Paid on", "Method", "Reference", "Refundable", "Status",
                 "Link", "Notes"])
    for cat, cost in shown:
        for p in cost.payments:
            rows.append([
                "Payments", cost.vendor_name, cat.name, KIND_LABELS.get(p.kind, p.kind),
                dollars(p.amount_cents), _day(p.due_on), _yes(p.paid), _day(p.paid_on),
                p.method, p.reference, _yes(p.refundable), payment_status(p),
                p.link_url, p.notes,
            ])
    rows.append([])

    rows.append(["Section", "Due", "Expense", "Category", "Type", "Amount (USD)",
                 "Refundable", "Status"])
    for due in overview.next_due:
        rows.append([
            "Upcoming", _day(due.due_on) or "No date", due.vendor_name, due.category_name,
            KIND_LABELS.get(due.kind, due.kind), dollars(due.amount_cents),
            _yes(due.refundable), "Overdue" if due.overdue else "Unpaid",
        ])

    return _write(rows)


def _write(rows: Iterable[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    # The byte-order mark tells Excel the file is UTF-8, so "é" and "&" read right.
    return "\ufeff" + out.getvalue()
