from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Literal, Optional
from datetime import date
from decimal import Decimal
import re
import json
from io import StringIO
from fastapi.responses import StreamingResponse
import pandas as pd
from pydantic import BaseModel, Field as PydField

from app.config import settings
from app.utils.email_match import UnsafeEmailError, normalise_email
from app.db.session import get_db
from app.db.models import (
    User, Wedding, WeddingMember, BudgetCategory, BudgetLine, AgentDecisionLog,
    Booking, Venue, Supplier, Quote,
)
from app.api.v1.endpoints.budget import MAX_CENTS
from app.utils.budget_compare import compare_quote
from app.utils import checklist as checklist_rules
from app.api.v1.access import (
    UNSAFE_EMAIL, bootstrap_emails, require_wedding_access, weddings_for_member,
)
from app.api.v1.endpoints.auth import get_current_user
from app.utils.tasks import enqueue_agent_task
from app.agents.concierge import run_concierge
from app.agents.planner import run_intake_planner
from app.agents.matcher import run_venue_matcher, run_supplier_matcher
from app.agents.privacy import PromptNotApproved
from app.api.v1.review import Approval, needs_review

router = APIRouter()

# Schema for creating a wedding profile (the setup form, PD-009)
class WeddingCreate(BaseModel):
    guest_count_estimate: int = PydField(gt=0)
    # The budget can be left blank while the couple decide it (PD-009). The setup form
    # sends the couple's own total in whole US cents, which the budget screen shows
    # (PD-004). The older float field is only the intake estimate, as before.
    budget_total_cents: Optional[int] = PydField(default=None, gt=0, le=MAX_CENTS)
    budget_total: Optional[float] = PydField(default=None, gt=0, le=MAX_CENTS / 100)
    currency: Literal["USD"] = "USD"
    region: str = PydField(min_length=1, max_length=120)
    ceremony_type: str = PydField(min_length=1, max_length=60)
    # Saved on the couple's profile only; not sent to the AI (PD-009, rule 3).
    couple_name: Optional[str] = None
    style_notes: Optional[str] = None
    wedding_date: Optional[date] = None
    wedding_date_start: Optional[date] = None
    wedding_date_end: Optional[date] = None


def _intake_budget(payload: WeddingCreate) -> tuple[Optional[int], Optional[float]]:
    """The budget as (couple's total in cents, intake estimate in dollars). Both are
    None when it's left blank, never 0. Only a total sent in cents is the couple's own
    total; the dollars-only field stays an estimate, as PD-004 set it up."""
    if payload.budget_total_cents is not None and payload.budget_total is not None:
        raise HTTPException(status_code=422, detail="Send the budget once, in cents or dollars")
    if payload.budget_total_cents is not None:
        # One exact conversion for the older readers (planner, matchers, concierge).
        return payload.budget_total_cents, float(Decimal(payload.budget_total_cents) / 100)
    return None, payload.budget_total


@router.post("/", response_model=Wedding, status_code=status.HTTP_201_CREATED)
async def create_wedding(
    payload: WeddingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submits a couple's wedding profile (Intake Form).

    Runs the intake_planner to check the profile. Venue and supplier
    matching doesn't run automatically: the catalogue doesn't cover this wedding's
    area yet (B11), so it runs only when the couple ask for it (PD-003).

    This app plans one wedding (PD-001), so only the couple's own sign-in emails
    (ACCESS_BOOTSTRAP_EMAILS) may create it, and nobody can create a second one.
    Everyone on that list becomes an owner (PD-002: both partners manage access).
    """
    try:
        creator_email = normalise_email(current_user.email)
    except UnsafeEmailError:
        raise HTTPException(status_code=403, detail=UNSAFE_EMAIL)
    couple_emails = bootstrap_emails()
    if not settings.DEVELOPMENT_MODE and creator_email not in couple_emails:
        raise HTTPException(status_code=403, detail="Only the couple can set up the wedding.")
    existing = await db.exec(
        select(WeddingMember.id).where(WeddingMember.user_id == current_user.id)
    )
    if existing.first() is not None:
        raise HTTPException(status_code=409, detail="You already have access to a wedding.")
    if couple_emails:
        # The couple's wedding already exists if any of their emails is on a list,
        # even after one partner was removed from it.
        theirs = await db.exec(
            select(WeddingMember.id).where(WeddingMember.email.in_(sorted(couple_emails)))
        )
        if theirs.first() is not None:
            raise HTTPException(status_code=409, detail="Your wedding has already been set up.")

    today = checklist_rules.wedding_today()
    if payload.wedding_date is not None and payload.wedding_date < today:
        # Same rule as the checklist's date control.
        raise HTTPException(status_code=422, detail="Please pick a date that hasn't passed yet")

    region = payload.region.strip()
    ceremony_type = payload.ceremony_type.strip()
    if not region or not ceremony_type:
        raise HTTPException(status_code=422, detail="Please fill in the place and the ceremony")

    total_cents, total_float = _intake_budget(payload)
    wedding = Wedding(
        couple_user_id=current_user.id,
        guest_count_estimate=payload.guest_count_estimate,
        budget_total=total_float,
        budget_total_cents=total_cents,
        currency=payload.currency,
        region=region,
        ceremony_type=ceremony_type,
        style_notes=payload.style_notes,
        wedding_date=payload.wedding_date,
        # The checklist's "Catch up" group counts from the day the date was set (PD-007).
        wedding_date_set_on=today if payload.wedding_date else None,
        wedding_date_start=payload.wedding_date_start,
        wedding_date_end=payload.wedding_date_end,
        status="intake"
    )
    
    db.add(wedding)
    await db.flush()
    # The creator and the other partner own the wedding on its access list (PD-002).
    db.add(WeddingMember(
        wedding_id=wedding.id, email=creator_email, level="owner", user_id=current_user.id,
    ))
    for email in sorted(couple_emails - {creator_email}):
        # Linked to an account at that partner's next verified sign-in.
        db.add(WeddingMember(wedding_id=wedding.id, email=email, level="owner"))

    # The couple's names go on their profile only (dev signup leaves a placeholder).
    # No agent prompt includes them (PD-009, rule 3).
    if payload.couple_name and current_user.name != payload.couple_name:
        current_user.name = payload.couple_name
        db.add(current_user)

    await db.commit()
    await db.refresh(wedding)

    # Draft the budget now, unless that needs the AI: then it waits until the couple
    # have checked what would be sent (PD-008), from the dashboard. Matching waits
    # until the couple ask (PD-003).
    try:
        if await needs_review(run_intake_planner, db, wedding.id, None) is None:
            await enqueue_agent_task(
                "intake-planner",
                {"wedding_id": wedding.id},
            )
    except Exception as e:
        # Log error but don't fail the request since DB record is committed
        import logging
        logging.getLogger(__name__).error(f"Failed to enqueue intake planner task on creation: {e}")

    # Direct execution may have updated the wedding in its own session.
    await db.refresh(wedding)
    return wedding


class WeddingUpdate(BaseModel):
    guest_count_estimate: Optional[int] = None
    budget_total: Optional[float] = PydField(default=None, gt=0)  # never 0 (PD-009)
    region: Optional[str] = None
    ceremony_type: Optional[str] = None
    style_notes: Optional[str] = None
    wedding_date: Optional[date] = None


@router.patch("/{wedding_id}", response_model=Wedding)
async def update_wedding(
    wedding_id: str,
    payload: WeddingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates a wedding profile (e.g. the couple correcting their budget after a
    guardrail warning). Resets status to 'intake' so the caller can re-run the
    planner against the corrected profile via POST /weddings/{id}/replan.
    """
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")

    updates = payload.model_dump(exclude_unset=True)
    today = checklist_rules.wedding_today()
    new_date = updates.get("wedding_date")
    if new_date is not None and new_date != wedding.wedding_date and new_date < today:
        # Same rule as the checklist's date control.
        raise HTTPException(status_code=422, detail="Please pick a date that hasn't passed yet")
    if "wedding_date" in updates and new_date != wedding.wedding_date:
        # The checklist's "Catch up" group counts from the day the date was set (PD-007).
        wedding.wedding_date_set_on = today if new_date else None
    for field, value in updates.items():
        setattr(wedding, field, value)
    if updates:
        # A changed profile means the existing plan is stale; mark for re-planning.
        wedding.status = "intake"
    db.add(wedding)
    await db.commit()
    await db.refresh(wedding)
    return wedding


@router.post("/{wedding_id}/replan", status_code=status.HTTP_202_ACCEPTED)
async def replan_wedding(
    wedding_id: str,
    force: bool = False,
    approval: Optional[Approval] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-runs the intake planner for an existing wedding.

    Used to recover from a failed or guardrail-blocked intake. `force=true`
    acknowledges the budget guardrail and builds the plan anyway. If the planner needs
    the AI, the first call returns the text to check and sends nothing (PD-008).
    """
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")
    approved = approval.approved_prompt if approval else None
    review = await needs_review(run_intake_planner, db, wedding_id, approved, force=force)
    if review:
        return review

    # Reset to intake so the dashboard shows the "building" state while it reruns.
    wedding.status = "intake"
    db.add(wedding)
    await db.commit()

    enqueued = await enqueue_agent_task(
        "intake-planner", {"wedding_id": wedding_id, "force": force, "approved_prompt": approved}
    )
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue intake planner task")
    return {
        "status": "completed" if settings.DIRECT_AGENT_EXECUTION else "pending",
        "message": "Intake planner finished." if settings.DIRECT_AGENT_EXECUTION
        else "Intake planner re-enqueued.",
        "force": force,
    }


@router.get("/", response_model=List[Wedding])
async def list_weddings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists weddings for the authenticated user.
    
    Weddings the user is on the access list for (PD-002).
    """
    return await weddings_for_member(db, current_user)


@router.get("/{wedding_id}", response_model=Wedding)
async def get_wedding(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Gets details for a specific wedding, verifying user access."""
    return await require_wedding_access(db, wedding_id, current_user, "viewer")


@router.get("/{wedding_id}/budget", response_model=List[BudgetLine])
async def get_wedding_budget(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the budget allocations for a wedding."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
        
    budget_result = await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding_id).order_by(BudgetLine.allocated_amount.desc())
    )
    return budget_result.all()


class BookingDetail(BaseModel):
    id: str
    wedding_id: str
    venue_id: Optional[str] = None
    supplier_id: Optional[str] = None
    status: str
    sourced_by_agent_id: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_kind: str  # "venue" | "supplier"
    vendor_category: Optional[str] = None
    vendor_location: Optional[str] = None
    pricing_summary: Optional[dict] = None
    matching_rationale: Optional[str] = None
    draft_inquiry_email: Optional[str] = None
    # Latest quote the couple has logged for this vendor (from quote_extractor)
    quote_total: Optional[float] = None
    quote_currency: Optional[str] = None
    quote_rationale: Optional[str] = None
    # The matching category in the couple's budget (PD-004), and how the quote compares
    # with its planned amount. See app/utils/budget_compare.py.
    budget_category_name: Optional[str] = None
    budget_match_key: Optional[str] = None
    planned_cents: Optional[int] = None
    budget_currency: Optional[str] = None
    budget_comparison: Optional[str] = None
    over_budget: Optional[bool] = None
    over_by_cents: Optional[int] = None


@router.get("/{wedding_id}/bookings", response_model=List[BookingDetail])
async def get_wedding_bookings(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the venue + supplier shortlist for a wedding, enriched with the
    vendor's name and the matcher agent's rationale + draft inquiry email.

    The rationale and draft email aren't stored on the Booking — they live in the
    matcher's AgentDecisionLog output. We join them back here so the UI can show
    *why* each vendor was picked and the ready-to-send email, instead of a bare id.
    """
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")

    bookings_result = await db.exec(
        select(Booking).where(Booking.wedding_id == wedding_id).order_by(Booking.created_at.asc())
    )
    bookings = bookings_result.all()

    # Resolve vendor names/details in two batched lookups.
    venues = {v.id: v for v in (await db.exec(select(Venue))).all()}
    suppliers = {s.id: s for s in (await db.exec(select(Supplier))).all()}

    # Build vendor_id -> {rationale, draft_email} from the most recent successful
    # matcher decisions (desc timestamp; first seen per vendor wins).
    logs_result = await db.exec(
        select(AgentDecisionLog)
        .where(
            AgentDecisionLog.wedding_id == wedding_id,
            AgentDecisionLog.agent_id.in_(["venue_matcher", "supplier_matcher"]),
            AgentDecisionLog.status == "success",
        )
        .order_by(AgentDecisionLog.timestamp.desc())
    )
    match_meta: dict[str, dict] = {}
    for log in logs_result.all():
        payload = log.output_payload or {}
        for item in payload.get("shortlist", []):
            vid = item.get("vendor_id")
            if vid and vid not in match_meta:
                match_meta[vid] = {
                    "rationale": item.get("matching_rationale"),
                    "email": item.get("draft_inquiry_email"),
                }

    # Latest quote per booking + the couple's budget categories, so each vendor card can
    # compare the quote with what they planned for that category.
    booking_ids = [b.id for b in bookings]
    latest_quote: dict[str, Quote] = {}
    if booking_ids:
        quotes_result = await db.exec(
            select(Quote).where(Quote.booking_id.in_(booking_ids)).order_by(Quote.created_at.desc())
        )
        for q in quotes_result.all():
            latest_quote.setdefault(q.booking_id, q)
    categories = (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id)
    )).all()

    def quote_fields(bid: str, vendor_category: str) -> dict:
        q = latest_quote.get(bid)
        if not q:
            return {}
        return {
            "quote_total": q.total_amount,
            "quote_currency": q.currency,
            "quote_rationale": q.rationale_text,
            **compare_quote(q.total_amount, q.currency, vendor_category, categories),
        }

    details: List[BookingDetail] = []
    for b in bookings:
        if b.venue_id:
            v = venues.get(b.venue_id)
            meta = match_meta.get(b.venue_id, {})
            details.append(BookingDetail(
                id=b.id, wedding_id=b.wedding_id, venue_id=b.venue_id, status=b.status,
                sourced_by_agent_id=b.sourced_by_agent_id,
                vendor_kind="venue",
                vendor_name=v.name if v else None,
                vendor_category=(v.venue_type if v else None),
                vendor_location=(v.region if v else None),
                pricing_summary=(v.pricing_summary if v else None),
                matching_rationale=meta.get("rationale"),
                draft_inquiry_email=meta.get("email"),
                **quote_fields(b.id, "venue"),
            ))
        else:
            s = suppliers.get(b.supplier_id)
            meta = match_meta.get(b.supplier_id, {})
            details.append(BookingDetail(
                id=b.id, wedding_id=b.wedding_id, supplier_id=b.supplier_id, status=b.status,
                sourced_by_agent_id=b.sourced_by_agent_id,
                vendor_kind="supplier",
                vendor_name=s.name if s else None,
                vendor_category=(s.category if s else None),
                vendor_location=(s.location if s else None),
                pricing_summary=(s.pricing_summary if s else None),
                matching_rationale=meta.get("rationale"),
                draft_inquiry_email=meta.get("email"),
                **quote_fields(b.id, s.category if s else ""),
            ))
    return details


@router.get("/{wedding_id}/logs", response_model=List[AgentDecisionLog])
async def get_wedding_agent_logs(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the Agent Decision Logs for a wedding (alias for decisions)."""
    return await get_wedding_agent_decisions(wedding_id, current_user, db)


@router.get("/{wedding_id}/decisions", response_model=List[AgentDecisionLog])
async def get_wedding_agent_decisions(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the XPRIZE-critical Agent Decision Logs for a wedding with traceable history."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
        
    logs_result = await db.exec(
        select(AgentDecisionLog).where(AgentDecisionLog.wedding_id == wedding_id).order_by(AgentDecisionLog.timestamp.desc())
    )
    return logs_result.all()


@router.post("/{wedding_id}/match", status_code=status.HTTP_202_ACCEPTED)
async def trigger_venue_matching(
    wedding_id: str,
    approval: Optional[Approval] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the venue matching agent, once the couple have checked what it sends
    (PD-008): the first call returns that text and sends nothing."""
    await require_wedding_access(db, wedding_id, current_user, "editor")
    approved = approval.approved_prompt if approval else None
    review = await needs_review(run_venue_matcher, db, wedding_id, approved)
    if review:
        return review

    enqueued = await enqueue_agent_task(
        "venue-matcher", {"wedding_id": wedding_id, "approved_prompt": approved})
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue venue matcher task")
        
    return {
        "status": "completed" if settings.DIRECT_AGENT_EXECUTION else "pending",
        "message": "Venue matching finished." if settings.DIRECT_AGENT_EXECUTION
        else "Venue matching agent enqueued successfully.",
    }


class SupplierMatchRequest(BaseModel):
    category: str
    approved_prompt: Optional[str] = None


@router.post("/{wedding_id}/suppliers", status_code=status.HTTP_202_ACCEPTED)
async def trigger_supplier_matching(
    wedding_id: str,
    payload: SupplierMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the supplier matching agent for a category, once the couple have checked
    what it sends (PD-008): the first call returns that text and sends nothing."""
    await require_wedding_access(db, wedding_id, current_user, "editor")
    approved = payload.approved_prompt
    review = await needs_review(run_supplier_matcher, db, wedding_id, approved, payload.category)
    if review:
        return review

    enqueued = await enqueue_agent_task("supplier-matcher", {
        "wedding_id": wedding_id, "category": payload.category, "approved_prompt": approved,
    })
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue supplier matcher task")
        
    return {
        "status": "completed" if settings.DIRECT_AGENT_EXECUTION else "pending",
        "message": "Supplier matching finished." if settings.DIRECT_AGENT_EXECUTION
        else f"Supplier matching agent for {payload.category} enqueued successfully.",
    }


class ConciergeRequest(BaseModel):
    message: str
    approved_prompt: Optional[str] = None


@router.post("/{wedding_id}/concierge")
async def ask_concierge(
    wedding_id: str,
    payload: ConciergeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answers a couple's question via the concierge agent, grounded in their real
    budget, checklist, and vendors. Runs synchronously (chat needs an immediate reply)
    and logs an AgentDecisionLog row per question.

    The first call returns the text that would go to the AI and sends nothing; the
    couple send it by repeating the call with that text as ``approved_prompt`` (PD-008)."""
    await require_wedding_access(db, wedding_id, current_user, "editor")

    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")

    unavailable = HTTPException(
        status_code=502, detail="The concierge is briefly unavailable — please try again.")
    try:
        review = await needs_review(run_concierge, db, wedding_id, payload.approved_prompt,
                                    message=message)
    except HTTPException:
        raise
    except Exception:
        raise unavailable
    if review:
        return review
    try:
        out = await run_concierge(db, wedding_id, message=message, trigger="couple_action",
                                  user_id=current_user.id, approved_prompt=payload.approved_prompt)
    except PromptNotApproved:
        # The plan changed between the check and the click: show the new text.
        review = await needs_review(run_concierge, db, wedding_id, payload.approved_prompt,
                                    message=message)
        if review:
            return review
        raise unavailable
    except Exception:
        raise unavailable

    return {"reply": out.get("reply", "")}


def mask_pii(text: str) -> str:
    if not text:
        return text
    # Mask email addresses
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
    # Mask phone numbers (+353 or 08x)
    text = re.sub(r'(\+353|0)\s*\d[\s\d]{7,10}', '[REDACTED_PHONE]', text)
    return text


@router.get("/{wedding_id}/decisions/export")
async def export_redacted_decision_logs(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Produces a PII-redacted CSV export of all decision logs for a wedding."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
        
    logs_result = await db.exec(
        select(AgentDecisionLog).where(AgentDecisionLog.wedding_id == wedding_id).order_by(AgentDecisionLog.timestamp.asc())
    )
    logs = logs_result.all()
    
    data = []
    for log in logs:
        raw_input = json.dumps(log.input_payload) if log.input_payload else "{}"
        raw_output = json.dumps(log.output_payload) if log.output_payload else "{}"
        
        data.append({
            "timestamp": log.timestamp.isoformat() if log.timestamp else "",
            "agent_id": log.agent_id,
            "status": log.status,
            "confidence": log.confidence_score,
            "latency_ms": log.latency_ms,
            "rationale": mask_pii(log.rationale_summary),
            "input_payload": mask_pii(raw_input),
            "output_payload": mask_pii(raw_output)
        })
        
    df = pd.DataFrame(data)
    stream = StringIO()
    df.to_csv(stream, index=False)
    
    response = StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f"attachment; filename=wedding_{wedding_id}_audit_log.csv"
    return response
