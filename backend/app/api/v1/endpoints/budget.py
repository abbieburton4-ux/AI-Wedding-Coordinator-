"""The couple's budget (PD-004): total, categories, vendor costs, payments, contributions.

Every amount is whole US cents and every sum here is integer arithmetic (rule 4).
Anyone on the access list can read the budget, including family (viewers); only
owners and editors can change it or ask for the AI split. A payment is marked paid
only by a signed-in owner or editor clicking it, never by an agent (rule 4), and
nothing here contacts anyone (rule 1).
"""
import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.budget_split import category_key, run_budget_splitter
from app.api.v1.access import require_wedding_access
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import (
    BudgetCategory, BudgetContribution, BudgetCost, BudgetPayment, User, utcnow,
)
from app.db.session import get_db

router = APIRouter()

# $10 million per amount: far above any wedding, and inside Postgres INTEGER (about
# $21 million in cents). Totals are summed in Python, so they can't overflow.
MAX_CENTS = 1_000_000_000


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


class CostIn(BaseModel):
    vendor_name: str = Name()
    quoted_cents: Optional[int] = Cents()


class CostPatch(BaseModel):
    vendor_name: Optional[str] = Name(None)
    quoted_cents: Optional[int] = Cents()
    category_id: Optional[str] = None


class PaymentIn(BaseModel):
    kind: Literal["deposit", "payment"] = "payment"
    amount_cents: int = Field(ge=1, le=MAX_CENTS)
    due_on: Optional[datetime.date] = None


class PaymentPatch(BaseModel):
    kind: Optional[Literal["deposit", "payment"]] = None
    amount_cents: Optional[int] = Field(default=None, ge=1, le=MAX_CENTS)
    due_on: Optional[datetime.date] = None


class PaidIn(BaseModel):
    paid: bool


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

# Where a "committed" figure comes from: the vendor's quote, the payments scheduled so
# far (no quote recorded), or a mix of both across several vendors.
Basis = Literal["none", "quote", "scheduled", "mixed"]


def _basis(parts: list) -> str:
    kinds = {p for p in parts if p != "none"}
    if not kinds:
        return "none"
    return kinds.pop() if len(kinds) == 1 else "mixed"


class PaymentOut(BaseModel):
    id: str
    cost_id: str
    kind: str
    amount_cents: int
    due_on: Optional[datetime.date]
    paid: bool
    paid_at: Optional[datetime.datetime]
    paid_by_name: Optional[str]


class CostOut(BaseModel):
    id: str
    category_id: str
    vendor_name: str
    quoted_cents: Optional[int]
    committed_cents: int
    committed_basis: Basis
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
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
    costs: List[CostOut]


class ContributionOut(BaseModel):
    id: str
    contributor: str
    amount_cents: int
    category_id: Optional[str]


class DueOut(BaseModel):
    payment_id: str
    category_name: str
    vendor_name: str
    kind: str
    amount_cents: int
    due_on: Optional[datetime.date]
    overdue: bool


class Totals(BaseModel):
    total_cents: Optional[int]
    planned_cents: int
    committed_cents: int
    committed_basis: Basis
    paid_cents: int
    remaining_cents: int
    overpaid_cents: int
    contributions_cents: int


class Overview(BaseModel):
    totals: Totals
    categories: List[CategoryOut]
    contributions: List[ContributionOut]
    next_due: List[DueOut]


# --- Helpers --------------------------------------------------------------------------

def _clean(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise HTTPException(status_code=422, detail="Please type a name")
    return text


async def _row(db: AsyncSession, model, row_id: str, wedding_id: str, what: str):
    row = (await db.exec(
        select(model).where(model.id == row_id, model.wedding_id == wedding_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"That {what} isn't in this budget")
    return row


async def _editor(db: AsyncSession, wedding_id: str, user: User):
    return await require_wedding_access(db, wedding_id, user, "editor")


def _committed(cost: BudgetCost, payments: list) -> tuple:
    """The quote if there is one, otherwise what's been scheduled so far, with which."""
    if cost.quoted_cents is not None:
        return cost.quoted_cents, "quote"
    if not payments:
        return 0, "none"
    return sum(p.amount_cents for p in payments), "scheduled"


async def _check_unique_name(db: AsyncSession, wedding_id: str, name: str,
                             except_id: Optional[str] = None) -> None:
    key = category_key(name)
    for row in (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id)
    )).all():
        if row.id != except_id and category_key(row.name) == key:
            raise HTTPException(status_code=409,
                                detail=f"You already have a category called {row.name}")


async def _overview(db: AsyncSession, wedding) -> Overview:
    wid = wedding.id
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

    today = datetime.date.today()
    names = {}
    out_categories = []
    for cat in categories:
        out_costs = []
        for cost in by_category.get(cat.id, []):
            pays = by_cost.get(cost.id, [])
            names[cost.id] = (cat.name, cost.vendor_name)
            committed, basis = _committed(cost, pays)
            paid = sum(p.amount_cents for p in pays if p.paid)
            # Paying one vendor more than agreed doesn't reduce what's owed to another,
            # so "still to pay" and "overpaid" are worked out per vendor, never netted.
            out_costs.append(CostOut(
                id=cost.id, category_id=cat.id, vendor_name=cost.vendor_name,
                quoted_cents=cost.quoted_cents,
                committed_cents=committed, committed_basis=basis, paid_cents=paid,
                remaining_cents=max(committed - paid, 0),
                overpaid_cents=max(paid - committed, 0),
                payments=[_payment_out(p, payers.get(p.paid_by_user_id)) for p in pays],
            ))
        out_categories.append(CategoryOut(
            id=cat.id, name=cat.name, planned_cents=cat.planned_cents,
            committed_basis=_basis([c.committed_basis for c in out_costs]),
            costs=out_costs, **_sums(out_costs),
        ))

    # Unpaid payments, soonest first; ones with no date yet go last.
    unpaid = [p for p in payments if not p.paid and p.cost_id in names]
    unpaid.sort(key=lambda p: (p.due_on is None, p.due_on or today, p.created_at))
    next_due = [DueOut(
        payment_id=p.id, category_name=names[p.cost_id][0], vendor_name=names[p.cost_id][1],
        kind=p.kind, amount_cents=p.amount_cents, due_on=p.due_on,
        overdue=p.due_on is not None and p.due_on < today,
    ) for p in unpaid]

    return Overview(
        totals=Totals(
            total_cents=wedding.budget_total_cents,
            planned_cents=sum(c.planned_cents or 0 for c in categories),
            committed_basis=_basis([c.committed_basis for c in out_categories]),
            contributions_cents=sum(c.amount_cents for c in contributions),
            **_sums(out_categories),
        ),
        categories=out_categories,
        contributions=[ContributionOut(
            id=c.id, contributor=c.contributor, amount_cents=c.amount_cents,
            category_id=c.category_id,
        ) for c in contributions],
        next_due=next_due,
    )


def _sums(rows: list) -> dict:
    return {field: sum(getattr(r, field) for r in rows) for field in (
        "committed_cents", "paid_cents", "remaining_cents", "overpaid_cents")}


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
    row = BudgetCost(wedding_id=wedding_id, category_id=category_id,
                     vendor_name=_clean(payload.vendor_name), quoted_cents=payload.quoted_cents)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{wedding_id}/budget/costs/{cost_id}", response_model=BudgetCost)
async def edit_cost(
    wedding_id: str, cost_id: str, payload: CostPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetCost, cost_id, wedding_id, "vendor cost")
    updates = payload.model_dump(exclude_unset=True)
    if "vendor_name" in updates:
        row.vendor_name = _clean(updates["vendor_name"] or "")
    if "quoted_cents" in updates:
        row.quoted_cents = updates["quoted_cents"]
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
    row = BudgetPayment(wedding_id=wedding_id, cost_id=cost_id, kind=payload.kind,
                        amount_cents=payload.amount_cents, due_on=payload.due_on)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _payment_out(row, None)


async def _payer_name(db: AsyncSession, row: BudgetPayment) -> Optional[str]:
    if not (row.paid and row.paid_by_user_id):
        return None
    payer = await db.get(User, row.paid_by_user_id)
    return payer.name if payer else None


def _payment_out(row: BudgetPayment, paid_by_name: Optional[str]) -> PaymentOut:
    return PaymentOut(
        id=row.id, cost_id=row.cost_id, kind=row.kind, amount_cents=row.amount_cents,
        due_on=row.due_on, paid=row.paid, paid_at=row.paid_at,
        paid_by_name=paid_by_name if row.paid else None,
    )


@router.patch("/{wedding_id}/budget/payments/{payment_id}", response_model=PaymentOut)
async def edit_payment(
    wedding_id: str, payment_id: str, payload: PaymentPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetPayment, payment_id, wedding_id, "payment")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("kind"):
        row.kind = updates["kind"]
    if updates.get("amount_cents") is not None:
        row.amount_cents = updates["amount_cents"]
    if "due_on" in updates:
        row.due_on = updates["due_on"]
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _payment_out(row, await _payer_name(db, row))


@router.put("/{wedding_id}/budget/payments/{payment_id}/paid", response_model=PaymentOut)
async def mark_paid(
    wedding_id: str, payment_id: str, payload: PaidIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """The only way a payment becomes paid: a signed-in owner or editor ticking it.

    Records who ticked it and when. Ticking an already-paid payment again keeps the
    original record; unticking clears both.
    """
    await _editor(db, wedding_id, current_user)
    row = await _row(db, BudgetPayment, payment_id, wedding_id, "payment")
    if payload.paid != row.paid:
        row.paid = payload.paid
        row.paid_at = utcnow() if payload.paid else None
        row.paid_by_user_id = current_user.id if payload.paid else None
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return _payment_out(row, await _payer_name(db, row))


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
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Asks the AI for a starting split of the couple's total. Saves nothing: the
    couple review it and use ``apply-split`` if they want it (PD-004, call b)."""
    wedding = await _editor(db, wedding_id, current_user)
    if not wedding.budget_total_cents:
        raise HTTPException(status_code=400, detail="Set your total budget first")
    names = (await db.exec(
        select(BudgetCategory.name).where(BudgetCategory.wedding_id == wedding_id)
        .order_by(BudgetCategory.created_at)
    )).all()
    try:
        out = await run_budget_splitter(
            db, wedding_id,
            total_cents=wedding.budget_total_cents, category_names=list(names),
            guest_count=wedding.guest_count_estimate, ceremony_type=wedding.ceremony_type,
            trigger="couple_action", user_id=current_user.id,
        )
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
