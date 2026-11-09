import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.internal import require_internal_caller
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.db.models import Booking, Wedding
from app.agents.planner import run_intake_planner
from app.agents.matcher import run_venue_matcher, run_supplier_matcher
from app.agents.extractor import run_quote_extractor, run_vendor_reply_reader

logger = logging.getLogger(__name__)
# Only our own task dispatcher may call these: they run agents and change data.
router = APIRouter(dependencies=[Depends(require_internal_caller)])


# Task Request Schema Definitions
# ``approved_prompt`` is the text the couple checked and clicked to send (PD-008).
# Without it, or if the text to send has changed, the agent's model call is refused.
class IntakePlannerTaskSchema(BaseModel):
    wedding_id: str
    force: bool = False
    approved_prompt: Optional[str] = None


class VenueMatcherTaskSchema(BaseModel):
    wedding_id: str
    approved_prompt: Optional[str] = None

class SupplierMatcherTaskSchema(BaseModel):
    wedding_id: str
    category: str
    approved_prompt: Optional[str] = None

class QuoteExtractorTaskSchema(BaseModel):
    booking_id: str
    email_body: str
    approved_prompt: Optional[str] = None


class VendorReplyTaskSchema(BaseModel):
    wedding_id: str
    vendor_id: str
    email_body: str
    approved_prompt: Optional[str] = None


@router.post("/intake-planner", status_code=status.HTTP_200_OK)
async def task_intake_planner(
    payload: IntakePlannerTaskSchema, 
    db: AsyncSession = Depends(get_db)
):
    """Worker task running the intake planner (draft budget).

    On success the wedding moves to 'planning' (set by the agent). Venue and supplier
    matching run separately, only when the couple ask for them (PD-003, B11).
    """
    logger.info(f"Worker Task: starting intake-planner for wedding {payload.wedding_id}")
    try:
        # Run agent
        result = await run_intake_planner(
            db, payload.wedding_id, force=payload.force, trigger="couple_action",
            approved_prompt=payload.approved_prompt,
        )

        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Worker Task: intake-planner failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/venue-matcher", status_code=status.HTTP_200_OK)
async def task_venue_matcher(
    payload: VenueMatcherTaskSchema,
    db: AsyncSession = Depends(get_db)
):
    """Worker task executing the venue matcher agent to shortlist venues."""
    logger.info(f"Worker Task: starting venue-matcher for wedding {payload.wedding_id}")
    try:
        result = await run_venue_matcher(db, payload.wedding_id, trigger="agent_initiated",
                                         approved_prompt=payload.approved_prompt)
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Worker Task: venue-matcher failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supplier-matcher", status_code=status.HTTP_200_OK)
async def task_supplier_matcher(
    payload: SupplierMatcherTaskSchema,
    db: AsyncSession = Depends(get_db)
):
    """Worker task executing the supplier matcher agent to shortlist vendors."""
    logger.info(f"Worker Task: starting supplier-matcher ({payload.category}) for wedding {payload.wedding_id}")
    try:
        result = await run_supplier_matcher(
            db, 
            payload.wedding_id, 
            payload.category, 
            trigger="agent_initiated",
            approved_prompt=payload.approved_prompt,
        )
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Worker Task: supplier-matcher failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quote-extractor", status_code=status.HTTP_200_OK)
async def task_quote_extractor(
    payload: QuoteExtractorTaskSchema,
    db: AsyncSession = Depends(get_db)
):
    """Worker task executing the quote extractor agent to parse vendor email text."""
    logger.info(f"Worker Task: starting quote-extractor for booking {payload.booking_id}")
    try:
        # Find booking to retrieve wedding ID
        result = await db.exec(select(Booking).where(Booking.id == payload.booking_id))
        booking = result.first()
        if not booking:
            raise ValueError(f"Booking {payload.booking_id} not found in database.")
            
        wedding_id = str(booking.wedding_id)
        
        result_dict = await run_quote_extractor(
            db, 
            wedding_id, 
            booking.id, 
            payload.email_body, 
            trigger="supplier_response",
            booking_id=booking.id,
            approved_prompt=payload.approved_prompt,
        )
        return {"status": "completed", "result": result_dict}
    except Exception as e:
        logger.error(f"Worker Task: quote-extractor failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vendor-reply", status_code=status.HTTP_200_OK)
async def task_vendor_reply(payload: VendorReplyTaskSchema, db: AsyncSession = Depends(get_db)):
    """Worker task: reads a reply to one of the couple's own vendors (B62)."""
    try:
        result_dict = await run_vendor_reply_reader(
            db, payload.wedding_id, payload.email_body, vendor_id=payload.vendor_id,
            trigger="supplier_response", approved_prompt=payload.approved_prompt,
        )
        return {"status": "completed", "result": result_dict}
    except Exception as e:
        # The decision log holds the detail; don't echo the pasted text or the error here.
        logger.error("Worker Task: vendor-reply failed: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="The vendor reply couldn't be read.")
