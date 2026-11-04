from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.db.models import Booking, User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.access import require_wedding_access
from app.utils.tasks import enqueue_agent_task

router = APIRouter()

class QuoteExtractionRequest(BaseModel):
    email_body: str

@router.post("/{booking_id}/quote", status_code=status.HTTP_202_ACCEPTED)
async def trigger_quote_extractor(
    booking_id: str,
    payload: QuoteExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Triggers the quote extractor agent in the background to parse a supplier's reply."""
    result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = result.first()
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")
    await require_wedding_access(db, booking.wedding_id, current_user, "editor")

    enqueued = await enqueue_agent_task("quote-extractor", {
        "booking_id": booking_id,
        "email_body": payload.email_body
    })
    if not enqueued:
        raise HTTPException(status_code=500, detail="Failed to enqueue quote extractor task")
        
    return {"status": "pending", "message": "Quote extraction agent enqueued successfully."}
