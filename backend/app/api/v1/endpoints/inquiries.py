from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.db.session import get_db
from app.db.models import Booking, User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.access import require_wedding_access
from app.utils.tasks import enqueue_agent_task
from app.agents.extractor import run_quote_extractor
from app.api.v1.review import MAX_PROMPT_CHARS, needs_review

router = APIRouter()

class QuoteExtractionRequest(BaseModel):
    email_body: str = Field(max_length=MAX_PROMPT_CHARS)
    approved_prompt: Optional[str] = Field(default=None, max_length=MAX_PROMPT_CHARS)

@router.post("/{booking_id}/quote", status_code=status.HTTP_202_ACCEPTED)
async def trigger_quote_extractor(
    booking_id: str,
    payload: QuoteExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Runs the quote extractor on a supplier's reply the couple pasted in.

    The first call returns the cleaned text that would go to the AI and sends nothing;
    the couple send it by repeating the call with that text as ``approved_prompt``
    (PD-008)."""
    result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = result.first()
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")
    await require_wedding_access(db, booking.wedding_id, current_user, "editor")
    review = await needs_review(run_quote_extractor, db, str(booking.wedding_id),
                                payload.approved_prompt, booking.id, payload.email_body)
    if review:
        return review

    enqueued = await enqueue_agent_task("quote-extractor", {
        "booking_id": booking_id,
        "email_body": payload.email_body,
        "approved_prompt": payload.approved_prompt,
    })
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue quote extractor task")
        
    return {
        "status": "completed" if settings.DIRECT_AGENT_EXECUTION else "pending",
        "message": "Quote extraction finished." if settings.DIRECT_AGENT_EXECUTION
        else "Quote extraction agent enqueued successfully.",
    }
