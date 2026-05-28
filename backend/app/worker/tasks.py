import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.db.models import Booking
from app.agents.planner import run_intake_planner
from app.agents.matcher import run_venue_matcher, run_supplier_matcher
from app.agents.extractor import run_quote_extractor

logger = logging.getLogger(__name__)
router = APIRouter()

# Task Request Schema Definitions
class IntakePlannerTaskSchema(BaseModel):
    wedding_id: str

class VenueMatcherTaskSchema(BaseModel):
    wedding_id: str

class SupplierMatcherTaskSchema(BaseModel):
    wedding_id: str
    category: str

class QuoteExtractorTaskSchema(BaseModel):
    booking_id: str
    email_body: str


@router.post("/intake-planner", status_code=status.HTTP_200_OK)
async def task_intake_planner(
    payload: IntakePlannerTaskSchema, 
    db: AsyncSession = Depends(get_db)
):
    """Worker task executing the intake planner agent to seed timeline and budget."""
    logger.info(f"Worker Task: starting intake-planner for wedding {payload.wedding_id}")
    try:
        # Run agent
        result = await run_intake_planner(db, payload.wedding_id, trigger="couple_action")
        
        # After seeding budget and timeline, automatically trigger venue and supplier matching in the background!
        logger.info(f"Intake completed. Enqueuing matcher jobs for wedding {payload.wedding_id}...")
        from app.utils.tasks import enqueue_agent_task
        await enqueue_agent_task("venue-matcher", {"wedding_id": payload.wedding_id})
        
        # We can also automatically trigger matching for core suppliers
        # e.g., florals, photography, music
        for category in ["photography", "florals", "music"]:
            await enqueue_agent_task("supplier-matcher", {
                "wedding_id": payload.wedding_id, 
                "category": category
            })
            
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
        result = await run_venue_matcher(db, payload.wedding_id, trigger="agent_initiated")
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
            trigger="agent_initiated"
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
            booking_id=booking.id
        )
        return {"status": "completed", "result": result_dict}
    except Exception as e:
        logger.error(f"Worker Task: quote-extractor failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
