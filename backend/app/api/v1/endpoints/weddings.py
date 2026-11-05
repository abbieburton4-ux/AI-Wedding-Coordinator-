from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
import re
import json
from io import StringIO
from fastapi.responses import StreamingResponse
import pandas as pd
from pydantic import BaseModel

from app.config import settings
from app.utils.email_match import UnsafeEmailError, normalise_email
from app.db.session import get_db
from app.db.models import (
    User, Wedding, WeddingMember, BudgetCategory, BudgetLine, TimelineItem, AgentDecisionLog,
    Booking, Venue, Supplier, Quote,
)
from app.utils.budget_compare import compare_quote
from app.api.v1.access import (
    UNSAFE_EMAIL, bootstrap_emails, require_wedding_access, weddings_for_member,
)
from app.api.v1.endpoints.auth import get_current_user
from app.utils.tasks import enqueue_agent_task
from app.agents.concierge import run_concierge

router = APIRouter()

# Schema for creating a wedding profile
class WeddingCreate(BaseModel):
    guest_count_estimate: int
    budget_total: float
    region: str
    ceremony_type: str
    couple_name: Optional[str] = None  # e.g. "Priya & David" — personalizes the plan + vendor emails
    style_notes: Optional[str] = None
    wedding_date: Optional[date] = None
    wedding_date_start: Optional[date] = None
    wedding_date_end: Optional[date] = None


@router.post("/", response_model=Wedding, status_code=status.HTTP_201_CREATED)
async def create_wedding(
    payload: WeddingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submits a couple's wedding profile (Intake Form).

    Runs the intake_planner to build the budget and timeline. Venue and supplier
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

    wedding = Wedding(
        couple_user_id=current_user.id,
        guest_count_estimate=payload.guest_count_estimate,
        budget_total=payload.budget_total,
        region=payload.region,
        ceremony_type=payload.ceremony_type,
        style_notes=payload.style_notes,
        wedding_date=payload.wedding_date,
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

    # Capture the couple's names on their profile so the planner agent and the
    # draft vendor emails address them by name (dev signup leaves a placeholder).
    if payload.couple_name and current_user.name != payload.couple_name:
        current_user.name = payload.couple_name
        db.add(current_user)

    await db.commit()
    await db.refresh(wedding)

    # Build the budget and timeline now. Matching waits until the couple ask (PD-003).
    try:
        await enqueue_agent_task(
            "intake-planner",
            {"wedding_id": wedding.id},
        )
    except Exception as e:
        # Log error but don't fail the request since DB record is committed
        import logging
        logging.getLogger(__name__).error(f"Failed to enqueue intake planner task on creation: {e}")

    return wedding


class WeddingUpdate(BaseModel):
    guest_count_estimate: Optional[int] = None
    budget_total: Optional[float] = None
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-runs the intake planner for an existing wedding.

    Used to recover from a failed or guardrail-blocked intake. `force=true`
    acknowledges the budget guardrail and builds the plan anyway.
    """
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")

    # Reset to intake so the dashboard shows the "building" state while it reruns.
    wedding.status = "intake"
    db.add(wedding)
    await db.commit()

    enqueued = await enqueue_agent_task(
        "intake-planner", {"wedding_id": wedding_id, "force": force}
    )
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue intake planner task")
    return {"status": "pending", "message": "Intake planner re-enqueued.", "force": force}


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


@router.get("/{wedding_id}/timeline", response_model=List[TimelineItem])
async def get_wedding_timeline(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the timeline milestones for a wedding."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
        
    timeline_result = await db.exec(
        select(TimelineItem).where(TimelineItem.wedding_id == wedding_id).order_by(TimelineItem.due_at.asc())
    )
    return timeline_result.all()


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the venue matching agent in the background."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")
        
    enqueued = await enqueue_agent_task("venue-matcher", {"wedding_id": wedding_id})
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue venue matcher task")
        
    return {"status": "pending", "message": "Venue matching agent enqueued successfully."}


class SupplierMatchRequest(BaseModel):
    category: str


@router.post("/{wedding_id}/suppliers", status_code=status.HTTP_202_ACCEPTED)
async def trigger_supplier_matching(
    wedding_id: str,
    payload: SupplierMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the supplier matching agent in the background for a specific category."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")
        
    enqueued = await enqueue_agent_task("supplier-matcher", {"wedding_id": wedding_id, "category": payload.category})
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue supplier matcher task")
        
    return {"status": "pending", "message": f"Supplier matching agent for {payload.category} enqueued successfully."}


class ConciergeRequest(BaseModel):
    message: str


@router.post("/{wedding_id}/concierge")
async def ask_concierge(
    wedding_id: str,
    payload: ConciergeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answers a couple's question via the concierge agent, grounded in their real
    budget, timeline, and vendors. Runs synchronously (chat needs an immediate reply)
    and logs an AgentDecisionLog row per question."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "editor")

    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")

    try:
        out = await run_concierge(db, wedding_id, message=message, trigger="couple_action", user_id=current_user.id)
    except Exception:
        raise HTTPException(status_code=502, detail="The concierge is briefly unavailable — please try again.")

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
