"""The couple's budget (PD-004, PD-013): total, categories, expenses, payments,
contributions.

Every amount is whole US cents and every sum here is integer arithmetic (rule 4); the
figures are worked out on read by ``utils/budget_math.py``.
Anyone on the access list can read the budget, including family (viewers); only
owners and editors can change it or ask for the AI split. A payment is marked paid
only by a signed-in owner or editor clicking it, never by an agent (rule 4), and
nothing here contacts anyone (rule 1).
"""
import datetime
from typing import List, Literal, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.budget_split import category_key, run_budget_splitter
from app.agents.privacy import PromptNotApproved
from app.api.v1.review import Approval, needs_review
from app.api.v1.access import require_wedding_access
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import (
    BudgetCategory, BudgetContribution, BudgetCost, BudgetPayment, CoupleVendor, User, utcnow,
)
from app.db.session import get_db
from app.utils.budget_math import add_up, basis_of, cost_figures, is_overdue
from app.utils.checklist import wedding_today

router = APIRouter()

# $10 million per amount: far above any wedding, and inside Postgres INTEGER (about
# $21 million in cents). Totals are summed in Python, so they can't overflow.
MAX_CENTS = 1_000_000_000
MAX_NOTES = 2000
MAX_LINK = 2000


def Cents(default=None):
    return Field(default=default, ge=0, le=MAX_CENTS)


def Name(default=...):
    return Field(default=default, min_length=1, max_length=120)


# --- Request bodies -------------------------------------------------------------------

class TotalIn(BaseModel):
    total_cents: Optional[int] = Field(default=None, ge=1, le=MAX_CENTS)


class CategoryIn(BaseModel):
    name: str = Name()
    planned_cents: Optional[int] = Cents()


class CategoryPatch(BaseModel):
    name: Optional[str] = Name(None)
    planned_cents: Optional[int] = Cents()


ContractStatus = Literal["none", "sent", "signed"]


def Short(default=None):
    return Field(default=default, max_length=120)


def Notes(default=None):
    return Field(default=default, max_length=MAX_NOTES)


def Link(default=None):
    return Field(default=default, max_length=MAX_LINK)


class CostIn(BaseModel):
    vendor_name: str = Name()
    quoted_cents: Optional[int] = Cents()
    estimated_cents: Optional[int] = Cents()
    final_cents: Optional[int] = Cents()
    contract_status: ContractStatus = "none"
    payment_method: Optional[str] = Short()
    notes: Optional[str] = Notes()
    link_url: Optional[str] = Link()
    couple_vendor_id: Optional[str] = None


class CostPatch(BaseModel):
    vendor_name: Optional[str] = Name(None)
    quoted_cents: Optional[int] = Cents()
    estimated_cents: Optional[int] = Cents()
    final_cents: Optional[int] = Cents()
    contract_status: Optional[ContractStatus] = None
    payment_method: Optional[str] = Short()
    notes: Optional[str] = Notes()
    link_url: Optional[str] = Link()
    couple_vendor_id: Optional[str] = None
    archived: Optional[bool] = None
    category_id: Optional[str] = None


class PaymentIn(BaseModel):
    kind: Literal["deposit", "payment"] = "payment"
    amount_cents: int = Field(ge=1, le=MAX_CENTS)
    due_on: Optional[datetime.date] = None
    refundable: bool = False
    method: Optional[str] = Short()
    reference: Optional[str] = Short()
    notes: Optional[str] = Notes()
    link_url: Optional[str] = Link()


class PaymentPatch(BaseModel):
    kind: Optional[Literal["deposit", "payment"]] = None
    amount_cents: Optional[int] = Field(default=None, ge=1, le=MAX_CENTS)
    due_on: Optional[datetime.date] = None
    refundable: Optional[bool] = None
    method: Optional[str] = Short()
    reference: Optional[str] = Short()
    notes: Optional[str] = Notes()
    link_url: Optional[str] = Link()
    # Only on a payment already ticked paid; ticking it is PUT .../paid.
    paid_on: Optional[datetime.date] = None


class PaidIn(BaseModel):
    paid: bool
    paid_on: Optional[datetime.date] = None


class ContributionIn(BaseModel):
    contributor: str = Name()
    amount_cents: int = Cents(...)
    category_id: Optional[str] = None


class ContributionPatch(BaseModel):
    contributor: Optional[str] = Name(None)
    amount_cents: Optional[int] = Cents()
    category_id: Optional[str] = None


class SplitLineIn(BaseModel):
    name: str = Name()
    planned_cents: int = Cents(...)


class ApplySplitIn(BaseModel):
    lines: List[SplitLineIn] = Field(min_length=1, max_length=40)


# --- Responses ------------------------------------------------------------------------

# Where a "committed" figure comes from: the final cost, the quote, the estimate, the
# payments scheduled so far (none of those recorded), or a mix across expenses.
Basis = Literal["none", "final", "quote", "estimate", "scheduled", "mixed"]
Status = Literal["unpaid", "partly_paid", "paid", "overdue"]


class PaymentOut(BaseModel):
    id: str
    cost_id: str
    kind: str
    amount_cents: int
    due_on: Optional[datetime.date]
    paid: bool
    paid_at: Optional[datetime.datetime]
    paid_by_name: Optional[str]
    paid_on: Optional[datetime.date]
    refundable: bool
    method: Optional[str]
    reference: Optional[str]
    notes: Optional[str]
    link_url: Optional[str]
    overdue: bool
    # How far over the expense's cost paid would be if this were ticked; 0 if it
    # wouldn't be (and always 0 for refundable or paid payments).
    would_overpay_cents: int


class VendorRef(BaseModel):
    """The linked vendor on the Vendors page: name and section only, no contacts."""
    id: str
    name: str
    section: str


class CostOut(BaseModel):
    id: str
    category_id: str
    vendor_name: str
    estimated_cents: Optional[int]
    quoted_cents: Optional[int]
    final_cents: Optional[int]
    contract_status: str
    payment_method: Optional[str]
    notes: Optional[str]
    link_url: Optional[str]
    vendor: Optional[VendorRef]
    archived: bool
    status: Status
    committed_cents: int
    committed_basis: Basis
    scheduled_cents: int
    over_scheduled_cents: int
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
    refundable_cents: int
    refundable_paid_cents: int
    payments: List[PaymentOut]


class CategoryOut(BaseModel):
    id: str
    name: str
    planned_cents: Optional[int]
    committed_cents: int
    committed_basis: Basis
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
    refundable_cents: int
    refundable_paid_cents: int
    # Every expense, archived ones included (flagged); the sums leave archived out.
    costs: List[CostOut]


class ContributionOut(BaseModel):
    id: str
    contributor: str
    amount_cents: int
    category_id: Optional[str]


class DueOut(BaseModel):
    payment_id: str
    cost_id: str
    category_name: str
    vendor_name: str
    kind: str
    amount_cents: int
    due_on: Optional[datetime.date]
    overdue: bool
    refundable: bool


class Totals(BaseModel):
    total_cents: Optional[int]
    planned_cents: int
    committed_cents: int
    committed_basis: Basis
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
    contributions_cents: int
    refundable_cents: int
    refundable_paid_cents: int


class Overview(BaseModel):
    totals: Totals
    categories: List[CategoryOut]
    contributions: List[ContributionOut]
    next_due: List[DueOut]
    # The day "overdue" is measured against: today in Chicago (B45).
    today: datetime.date


# --- Helpers --------------------------------------------------------------------------

def _today() -> datetime.date:
    # Chicago's date, as the checklist uses (B45). One place, so tests can fix it.
    return wedding_today()


def _clean(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise HTTPException(status_code=422, detail="Please type a name")
    return text


def _short(text: Optional[str]) -> Optional[str]:
    """A one-line field (method, reference): spaces tidied, blank means none."""
    if text is None:
        return None
    return " ".join(text.split()) or None


def _notes(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return text.strip() or None


def _link(text: Optional[str]) -> Optional[str]:
    """A pasted link, such as a Google Drive file. Only web links: any other scheme
    could run or open something on the reader's device when clicked."""
    if text is None or not text.strip():
        return None
    url = text.strip()
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        parts, host = None, None
    # A user name or password in a link ("https://drive.google.com@other.site/") hides
    # where it really goes, so it's refused along with spaces and control characters.
    if (parts is None or parts.scheme.lower() not in ("http", "https") or not host
            or "@" in parts.netloc
            or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url)):
        raise HTTPException(status_code=422,
                            detail="Please paste a full web link starting with https://")
    return url


async def _row(db: AsyncSession, model, row_id: str, wedding_id: str, what: str):
    row = (await db.exec(
        select(model).where(model.id == row_id, model.wedding_id == wedding_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"That {what} isn't in this budget")
    return row


async def _vendor(db: AsyncSession, vendor_id: Optional[str], wedding_id: str) -> Optional[str]:
    """A vendor id from this wedding's Vendors page, or None to unlink."""
    if not vendor_id:
        return None
    found = (await db.exec(select(CoupleVendor.id).where(
        CoupleVendor.id == vendor_id, CoupleVendor.wedding_id == wedding_id))).first()
    if not found:
        raise HTTPException(status_code=404, detail="That vendor isn't on your Vendors page")
    return vendor_id


async def _editor(db: AsyncSession, wedding_id: str, user: User):
    return await require_wedding_access(db, wedding_id, user, "editor")


async def _check_unique_name(db: AsyncSession, wedding_id: str, name: str,
                             except_id: Optional[str] = None) -> None:
    key = category_key(name)
    for row in (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id)
    )).all():
        if row.id != except_id and category_key(row.name) == key:
            raise HTTPException(status_code=409,
                                detail=f"You already have a category called {row.name}")


def _payment_out(row: BudgetPayment, paid_by_name: Optional[str], figures,
                 today: datetime.date) -> PaymentOut:
    return PaymentOut(
        id=row.id, cost_id=row.cost_id, kind=row.kind, amount_cents=row.amount_cents,
        due_on=row.due_on, paid=row.paid, paid_at=row.paid_at,
        paid_by_name=paid_by_name if row.paid else None,
        paid_on=row.paid_on if row.paid else None, refundable=row.refundable,
        method=row.method, reference=row.reference, notes=row.notes,
        link_url=row.link_url, overdue=is_overdue(row, today),
        would_overpay_cents=figures.would_overpay.get(row.id, 0),
    )


def _cost_out(cost: BudgetCost, pays: list, payers: dict, vendors: dict,
              today: datetime.date) -> CostOut:
    f = cost_figures(cost, pays, today)
    v = vendors.get(cost.couple_vendor_id)
    return CostOut(
        id=cost.id, category_id=cost.category_id, vendor_name=cost.vendor_name,
        estimated_cents=cost.estimated_cents, quoted_cents=cost.quoted_cents,
        final_cents=cost.final_cents, contract_status=cost.contract_status,
        payment_method=cost.payment_method, notes=cost.notes, link_url=cost.link_url,
        vendor=VendorRef(id=v.id, name=v.name, section=v.section) if v else None,
        archived=cost.archived, status=f.status,
        committed_cents=f.committed_cents, committed_basis=f.committed_basis,
        scheduled_cents=f.scheduled_cents, over_scheduled_cents=f.over_scheduled_cents,
        paid_cents=f.paid_cents, remaining_cents=f.remaining_cents,
        overpaid_cents=f.overpaid_cents, refundable_cents=f.refundable_cents,
        refundable_paid_cents=f.refundable_paid_cents,
        payments=[_payment_out(p, payers.get(p.paid_by_user_id), f, today) for p in pays],
    )


async def _overview(db: AsyncSession, wedding) -> Overview:
    wid = wedding.id
    today = _today()
    categories = (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wid)
        .order_by(BudgetCategory.created_at, BudgetCategory.id)
    )).all()
    costs = (await db.exec(
        select(BudgetCost).where(BudgetCost.wedding_id == wid)
        .order_by(BudgetCost.created_at, BudgetCost.id)
    )).all()
    payments = (await db.exec(
        select(BudgetPayment).where(BudgetPayment.wedding_id == wid)
        .order_by(BudgetPayment.due_on, BudgetPayment.created_at, BudgetPayment.id)
    )).all()
    contributions = (await db.exec(
        select(BudgetContribution).where(BudgetContribution.wedding_id == wid)
        .order_by(BudgetContribution.created_at, BudgetContribution.id)
    )).all()
    vendors = {v.id: v for v in (await db.exec(
        select(CoupleVendor).where(CoupleVendor.wedding_id == wid))).all()}
    payer_ids = {p.paid_by_user_id for p in payments if p.paid_by_user_id}
    payers = {}
    if payer_ids:
        payers = {u.id: u.name for u in (await db.exec(
            select(User).where(User.id.in_(sorted(payer_ids)))
        )).all()}

    by_cost: dict = {}
    for p in payments:
        by_cost.setdefault(p.cost_id, []).append(p)
    by_category: dict = {}
    for c in costs:
        by_category.setdefault(c.category_id, []).append(c)

    names = {}
    out_categories = []
    for cat in categories:
        out_costs = []
        for cost in by_category.get(cat.id, []):
            if not cost.archived:
                names[cost.id] = (cat.name, cost.vendor_name)
            # Paying one vendor more than agreed doesn't reduce what's owed to another,
            # so "still to pay" and "overpaid" are worked out per expense, never netted.
            out_costs.append(_cost_out(cost, by_cost.get(cost.id, []), payers, vendors, today))
        counted = [c for c in out_costs if not c.archived]
        out_categories.append(CategoryOut(
            id=cat.id, name=cat.name, planned_cents=cat.planned_cents,
            committed_basis=basis_of(c.committed_basis for c in counted),
            costs=out_costs, **add_up(counted),
        ))

    # Unpaid payments on expenses still in play, soonest first; undated ones last.
    unpaid = [p for p in payments if not p.paid and p.cost_id in names]
    unpaid.sort(key=lambda p: (p.due_on is None, p.due_on or today, p.created_at))
    next_due = [DueOut(
        payment_id=p.id, cost_id=p.cost_id, category_name=names[p.cost_id][0],
        vendor_name=names[p.cost_id][1], kind=p.kind, amount_cents=p.amount_cents,
        due_on=p.due_on, overdue=is_overdue(p, today), refundable=p.refundable,
    ) for p in unpaid]

    return Overview(
        totals=Totals(
            total_cents=wedding.budget_total_cents,
            planned_cents=sum(c.planned_cents or 0 for c in categories),
            committed_basis=basis_of(c.committed_basis for c in out_categories),
            contributions_cents=sum(c.amount_cents for c in contributions),
            **add_up(out_categories),
        ),
        categories=out_categories,
        contributions=[ContributionOut(
            id=c.id, contributor=c.contributor, amount_cents=c.amount_cents,
            category_id=c.category_id,
        ) for c in contributions],
        next_due=next_due,
        today=today,
    )


async def _payment_response(db: AsyncSession, row: BudgetPayment) -> PaymentOut:
    """One payment, with the figures that depend on the rest of its expense."""
    cost = await db.get(BudgetCost, row.cost_id)
    pays = (await db.exec(select(BudgetPayment).where(
        BudgetPayment.cost_id == row.cost_id))).all()
    today = _today()
    payer = None
    if row.paid and row.paid_by_user_id:
        user = await db.get(User, row.paid_by_user_id)
        payer = user.name if user else None
    return _payment_out(row, payer, cost_figures(cost, list(pays), today), today)


# --- Routes ---------------------------------------------------------------------------

@router.get("/{wedding_id}/budget/overview", response_model=Overview)
async def budget_overview(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything on the budget screen, with totals worked out in cents."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
    return await _overview(db, wedding)


@router.put("/{wedding_id}/budget/total", response_model=Totals)
async def set_total(
    wedding_id: str, payload: TotalIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Sets the couple's total, or clears it with null."""
    wedding = await _editor(db, wedding_id, current_user)
    wedding.budget_total_cents = payload.total_cents
    db.add(wedding)
    await db.commit()
    await db.refresh(wedding)
    return (await _overview(db, wedding)).totals


@router.post("/{wedding_id}/budget/categories", status_code=status.HTTP_201_CREATED,
             response_model=BudgetCategory)
async def add_category(
    wedding_id: str, payload: CategoryIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    name = _clean(payload.name)
    await _check_unique_name(db, wedding_id, name)
    row = BudgetCategory(wedding_id=wedding_id, name=name, planned_cents=payload.planned_cents)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{wedding_id}/budget/categories/{category_id}", response_model=BudgetCategory)
async def edit_category(
    wedding_id: str, category_id: str, payload: CategoryPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetCategory, category_id, wedding_id, "category")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        name = _clean(updates["name"] or "")
        await _check_unique_name(db, wedding_id, name, except_id=row.id)
        row.name = name
    if "planned_cents" in updates:
        row.planned_cents = updates["planned_cents"]
    row.updated_at = utcnow()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _delete_costs(db: AsyncSession, costs: list) -> None:
    # Children are removed here, not left to ON DELETE CASCADE, because SQLite only
    # enforces foreign keys when asked to.
    for cost in costs:
        for p in (await db.exec(select(BudgetPayment).where(BudgetPayment.cost_id == cost.id))).all():
            await db.delete(p)
        await db.delete(cost)


@router.delete("/{wedding_id}/budget/categories/{category_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_category(
    wedding_id: str, category_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Removes a category with its vendor costs and payments. Contributions towards it
    stay, no longer tied to a category."""
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetCategory, category_id, wedding_id, "category")
    costs = (await db.exec(select(BudgetCost).where(BudgetCost.category_id == row.id))).all()
    await _delete_costs(db, list(costs))
    for c in (await db.exec(
        select(BudgetContribution).where(BudgetContribution.category_id == row.id)
    )).all():
        c.category_id = None
        db.add(c)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wedding_id}/budget/categories/{category_id}/costs",
             status_code=status.HTTP_201_CREATED, response_model=BudgetCost)
async def add_cost(
    wedding_id: str, category_id: str, payload: CostIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    await _row(db, BudgetCategory, category_id, wedding_id, "category")
    row = BudgetCost(
        wedding_id=wedding_id, category_id=category_id,
        vendor_name=_clean(payload.vendor_name), quoted_cents=payload.quoted_cents,
        estimated_cents=payload.estimated_cents, final_cents=payload.final_cents,
        contract_status=payload.contract_status,
        payment_method=_short(payload.payment_method), notes=_notes(payload.notes),
        link_url=_link(payload.link_url),
        couple_vendor_id=await _vendor(db, payload.couple_vendor_id, wedding_id),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{wedding_id}/budget/costs/{cost_id}", response_model=BudgetCost)
async def edit_cost(
    wedding_id: str, cost_id: str, payload: CostPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Changes an expense. A field left out stays as it is; null clears an optional one.
    ``archived`` keeps the expense and its payments but leaves them out of the totals."""
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetCost, cost_id, wedding_id, "vendor cost")
    updates = payload.model_dump(exclude_unset=True)
    if "vendor_name" in updates:
        row.vendor_name = _clean(updates["vendor_name"] or "")
    for field in ("quoted_cents", "estimated_cents", "final_cents"):
        if field in updates:
            setattr(row, field, updates[field])
    if updates.get("contract_status"):
        row.contract_status = updates["contract_status"]
    if "payment_method" in updates:
        row.payment_method = _short(updates["payment_method"])
    if "notes" in updates:
        row.notes = _notes(updates["notes"])
    if "link_url" in updates:
        row.link_url = _link(updates["link_url"])
    if "couple_vendor_id" in updates:
        row.couple_vendor_id = await _vendor(db, updates["couple_vendor_id"], wedding_id)
    if updates.get("archived") is not None:
        row.archived = updates["archived"]
    if updates.get("category_id"):
        await _row(db, BudgetCategory, updates["category_id"], wedding_id, "category")
        row.category_id = updates["category_id"]
    row.updated_at = utcnow()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{wedding_id}/budget/costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cost(
    wedding_id: str, cost_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetCost, cost_id, wedding_id, "vendor cost")
    await _delete_costs(db, [row])
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wedding_id}/budget/costs/{cost_id}/payments",
             status_code=status.HTTP_201_CREATED, response_model=PaymentOut)
async def add_payment(
    wedding_id: str, cost_id: str, payload: PaymentIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Adds a deposit or payment, always unpaid. Ticking it paid is a separate click."""
    await _editor(db, wedding_id, current_user)
    await _row(db, BudgetCost, cost_id, wedding_id, "vendor cost")
    row = BudgetPayment(
        wedding_id=wedding_id, cost_id=cost_id, kind=payload.kind,
        amount_cents=payload.amount_cents, due_on=payload.due_on,
        refundable=payload.refundable, method=_short(payload.method),
        reference=_short(payload.reference), notes=_notes(payload.notes),
        link_url=_link(payload.link_url),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _payment_response(db, row)


def _paid_on(day: Optional[datetime.date]) -> Optional[datetime.date]:
    if day is not None and day > _today():
        raise HTTPException(status_code=422, detail="The date paid can't be in the future")
    return day


@router.patch("/{wedding_id}/budget/payments/{payment_id}", response_model=PaymentOut)
async def edit_payment(
    wedding_id: str, payment_id: str, payload: PaymentPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Changes a payment's details. It never ticks or unticks it; that's PUT .../paid."""
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetPayment, payment_id, wedding_id, "payment")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("kind"):
        row.kind = updates["kind"]
    if updates.get("amount_cents") is not None:
        row.amount_cents = updates["amount_cents"]
    if "due_on" in updates:
        row.due_on = updates["due_on"]
    if updates.get("refundable") is not None:
        row.refundable = updates["refundable"]
    for field in ("method", "reference"):
        if field in updates:
            setattr(row, field, _short(updates[field]))
    if "notes" in updates:
        row.notes = _notes(updates["notes"])
    if "link_url" in updates:
        row.link_url = _link(updates["link_url"])
    if "paid_on" in updates:
        if updates["paid_on"] is not None and not row.paid:
            raise HTTPException(status_code=422,
                                detail="Tick the payment as paid before giving the date paid")
        row.paid_on = _paid_on(updates["paid_on"])
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _payment_response(db, row)


@router.put("/{wedding_id}/budget/payments/{payment_id}/paid", response_model=PaymentOut)
async def mark_paid(
    wedding_id: str, payment_id: str, payload: PaidIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """The only way a payment becomes paid: a signed-in owner or editor ticking it.

    Records who ticked it and when, and the date paid if they give one. Ticking an
    already-paid payment again keeps the original record (a new date paid replaces
    the old one); unticking clears all three. Ticking a payment that takes paid over
    the expense's cost is allowed: the screen warns first, and it shows as overpaid.
    """
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetPayment, payment_id, wedding_id, "payment")
    if not payload.paid and payload.paid_on is not None:
        raise HTTPException(status_code=422, detail="An unpaid payment has no date paid")
    changed = False
    if payload.paid != row.paid:
        row.paid = payload.paid
        row.paid_at = utcnow() if payload.paid else None
        row.paid_by_user_id = current_user.id if payload.paid else None
        row.paid_on = None
        changed = True
    if payload.paid and payload.paid_on is not None:
        row.paid_on = _paid_on(payload.paid_on)
        changed = True
    if changed:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return await _payment_response(db, row)


@router.delete("/{wedding_id}/budget/payments/{payment_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment(
    wedding_id: str, payment_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetPayment, payment_id, wedding_id, "payment")
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wedding_id}/budget/contributions", status_code=status.HTTP_201_CREATED,
             response_model=ContributionOut)
async def add_contribution(
    wedding_id: str, payload: ContributionIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    if payload.category_id:
        await _row(db, BudgetCategory, payload.category_id, wedding_id, "category")
    row = BudgetContribution(wedding_id=wedding_id, contributor=_clean(payload.contributor),
                             amount_cents=payload.amount_cents, category_id=payload.category_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return ContributionOut(**row.model_dump(include={"id", "contributor", "amount_cents",
                                                      "category_id"}))


@router.patch("/{wedding_id}/budget/contributions/{contribution_id}",
              response_model=ContributionOut)
async def edit_contribution(
    wedding_id: str, contribution_id: str, payload: ContributionPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetContribution, contribution_id, wedding_id, "contribution")
    updates = payload.model_dump(exclude_unset=True)
    if "contributor" in updates:
        row.contributor = _clean(updates["contributor"] or "")
    if updates.get("amount_cents") is not None:
        row.amount_cents = updates["amount_cents"]
    if "category_id" in updates:
        if updates["category_id"]:
            await _row(db, BudgetCategory, updates["category_id"], wedding_id, "category")
        row.category_id = updates["category_id"] or None
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return ContributionOut(**row.model_dump(include={"id", "contributor", "amount_cents",
                                                      "category_id"}))


@router.delete("/{wedding_id}/budget/contributions/{contribution_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_contribution(
    wedding_id: str, contribution_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetContribution, contribution_id, wedding_id, "contribution")
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wedding_id}/budget/suggest-split")
async def suggest_split(
    wedding_id: str,
    approval: Optional[Approval] = Body(default=None),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Asks the AI for a starting split of the couple's total. Saves nothing: the
    couple review it and use ``apply-split`` if they want it (PD-004, call b).

    The first call returns the text that would go to the AI and sends nothing; the
    couple send it by repeating the call with that text as ``approved_prompt`` (PD-008)."""
    wedding = await _editor(db, wedding_id, current_user)
    if not wedding.budget_total_cents:
        raise HTTPException(status_code=400, detail="Set your total budget first")
    names = (await db.exec(
        select(BudgetCategory.name).where(BudgetCategory.wedding_id == wedding_id)
        .order_by(BudgetCategory.created_at, BudgetCategory.id)
    )).all()
    facts = dict(total_cents=wedding.budget_total_cents, category_names=list(names),
                 guest_count=wedding.guest_count_estimate, ceremony_type=wedding.ceremony_type)
    approved = approval.approved_prompt if approval else None
    review = await needs_review(run_budget_splitter, db, wedding_id, approved, **facts)
    if review:
        return review
    try:
        out = await run_budget_splitter(
            db, wedding_id, **facts, approved_prompt=approved,
            trigger="couple_action", user_id=current_user.id,
        )
    except PromptNotApproved:
        review = await needs_review(run_budget_splitter, db, wedding_id, approved, **facts)
        if review:
            return review
        raise HTTPException(status_code=502,
                            detail="The suggestion didn't work this time. Please try again.")
    except Exception:
        raise HTTPException(status_code=502,
                            detail="The suggestion didn't work this time. Please try again.")
    if out.get("status") == "blocked":
        raise HTTPException(status_code=422,
                            detail="The suggestion didn't pass our checks. Please try again.")
    return {"total_cents": out["total_cents"], "lines": out["lines"],
            "rationale_summary": out.get("rationale_summary", "")}


@router.post("/{wedding_id}/budget/apply-split", response_model=Overview)
async def apply_split(
    wedding_id: str, payload: ApplySplitIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Uses a split the couple reviewed (and maybe edited or trimmed): sets each named
    category's planned amount, adding categories that don't exist yet. Leaves other
    categories, vendor costs and payments alone.

    The lines must add up to exactly the couple's total, and each must name a different
    category. Names are matched ignoring case, spaces and underscores; if that matches
    two of the couple's categories, nothing is changed and they're asked to rename one.
    """
    wedding = await _editor(db, wedding_id, current_user)
    if not wedding.budget_total_cents:
        raise HTTPException(status_code=400, detail="Set your total budget first")
    lines = [(_clean(line.name), line.planned_cents) for line in payload.lines]
    keys = [category_key(name) for name, _ in lines]
    if len(set(keys)) != len(keys):
        raise HTTPException(status_code=422, detail="Each category can only appear once")
    if sum(cents for _, cents in lines) != wedding.budget_total_cents:
        raise HTTPException(status_code=409,
                            detail="The amounts need to add up to your total budget")

    existing: dict = {}
    for row in (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id)
    )).all():
        existing.setdefault(category_key(row.name), []).append(row)
    for key, (name, _) in zip(keys, lines):
        if len(existing.get(key, [])) > 1:
            names = " and ".join(r.name for r in existing[key])
            raise HTTPException(
                status_code=409,
                detail=f"You have two categories that look the same ({names}). "
                "Rename or remove one, then use the split.",
            )
    for key, (name, cents) in zip(keys, lines):
        row = existing[key][0] if key in existing else BudgetCategory(
            wedding_id=wedding_id, name=name)
        row.planned_cents = cents
        row.updated_at = utcnow()
        db.add(row)
    await db.commit()
    return await _overview(db, wedding)
