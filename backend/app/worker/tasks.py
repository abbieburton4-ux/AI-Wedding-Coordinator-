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
    force: bool = False

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
        result = await run_intake_planner(
            db, payload.wedding_id, force=payload.force, trigger="couple_action"
        )

        # If the intake was blocked by a guardrail (e.g. unrealistic budget) the
        # wedding stays in 'intake' with no budget seeded — don't waste matcher
        # calls. The couple resolves it from the dashboard (adjust / continue).
        if isinstance(result, dict) and result.get("status") == "blocked":
            logger.info(f"Intake blocked by guardrail for wedding {payload.wedding_id}; skipping matcher cascade.")
            return {"status": "blocked", "result": result}

        # After seeding budget and timeline, cascade into venue + supplier matching.
        # Run these SEQUENTIALLY (not as 4 concurrent tasks): the agent holds a DB
        # write transaction open across its Gemini call, so concurrent matchers
        # deadlock SQLite ("database is locked"); sequential also stays under
        # free-tier rate limits. Each is best-effort — one failure (e.g. a rate
        # limit) must not abort the rest of the shortlist.
        logger.info(f"Intake completed. Running matcher cascade for wedding {payload.wedding_id}...")
        cascade = [
            (run_venue_matcher, {}),
            (run_supplier_matcher, {"category": "photography"}),
            (run_supplier_matcher, {"category": "florals"}),
            (run_supplier_matcher, {"category": "music"}),
        ]
        for runner, extra in cascade:
            try:
                await runner(db, payload.wedding_id, trigger="agent_initiated", **extra)
            except Exception as e:
                logger.error(f"Cascade {runner.__name__} failed (continuing): {e}")

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
