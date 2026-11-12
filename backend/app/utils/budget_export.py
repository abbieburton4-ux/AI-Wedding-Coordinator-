"""Labels and the formula-guard prefixes for the budget's Excel download (PD-019).

``utils/budget_xlsx.py`` builds the file from these. ``FORMULA_STARTS`` lists what a
spreadsheet may read as the start of a formula; a text cell starting with one is kept as
text.
"""

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
    "none": "Nothing yet", "final": "Actual cost", "quote": "Quote", "estimate": "Estimate",
    "scheduled": "Payments scheduled", "mixed": "Mixed",
}
CONTRACT_LABELS = {"none": "None", "sent": "Sent", "signed": "Signed"}
KIND_LABELS = {"deposit": "Deposit", "payment": "Payment"}

# What a spreadsheet may treat as the start of a formula: OWASP's list, plus the
# full-width forms some keyboards type, which some spreadsheets read the same way.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n",
                  "\uff1d", "\uff0b", "\uff0d", "\uff20")


def payment_status(payment) -> str:
    if payment.paid:
        return "Paid"
    return "Overdue" if payment.overdue else "Unpaid"
