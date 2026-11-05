"""Compare a vendor's quote with the couple's own budget (PD-004, B42).

The budget is whole US cents. A quote is compared only with the planned amount of the
budget category whose name matches the vendor's catalogue category (``category_key``,
so 'hair_makeup' matches 'Hair makeup'), and only when the quote is also in US dollars.
Otherwise there is no comparison and no flag, rather than a guessed one.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from app.agents.budget_split import category_key

BUDGET_CURRENCY = "USD"


def to_cents(amount) -> Optional[int]:
    """A quote amount as whole cents via Decimal, or None if it isn't a finite number."""
    if amount is None or isinstance(amount, bool):
        return None
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compare_quote(quote_total, quote_currency: Optional[str], vendor_category: Optional[str],
                  categories: list) -> dict:
    """Fields for a vendor card. ``categories`` are the wedding's ``BudgetCategory`` rows.

    ``budget_comparison`` is one of ``over``, ``within``, ``no_category``,
    ``no_planned_amount``, ``currency_mismatch`` or ``no_quote``; ``over_budget`` and
    ``over_by_cents`` are set only for ``over`` and ``within``. A planned amount of $0 is
    a real plan, so any quote above it is over. ``budget_match_key`` is the category name
    the card looks for, so the UI can say which category is missing.
    """
    key = category_key(vendor_category)
    match = next((c for c in categories if key and category_key(c.name) == key), None)
    out = {
        "budget_category_name": match.name if match else None,
        "planned_cents": match.planned_cents if match else None,
        "budget_match_key": key or None,
        "budget_currency": BUDGET_CURRENCY,
        "over_budget": None,
        "over_by_cents": None,
    }
    quote_cents = to_cents(quote_total)
    if quote_cents is None:
        return {**out, "budget_comparison": "no_quote"}
    if (quote_currency or "").strip().upper() != BUDGET_CURRENCY:
        return {**out, "budget_comparison": "currency_mismatch"}
    if match is None:
        return {**out, "budget_comparison": "no_category"}
    if match.planned_cents is None:
        return {**out, "budget_comparison": "no_planned_amount"}
    over_by = quote_cents - match.planned_cents
    return {
        **out,
        "budget_comparison": "over" if over_by > 0 else "within",
        "over_budget": over_by > 0,
        "over_by_cents": max(over_by, 0),
    }
