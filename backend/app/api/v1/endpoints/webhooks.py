import re
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import Booking
from app.utils.tasks import enqueue_agent_task
from app.api.v1.internal import require_inbound_email_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Regex to capture booking ID from recipient: booking-<id>@inbox.venueflow.ie
BOOKING_EMAIL_RE = re.compile(r"booking-([a-zA-Z0-9_]+)@inbox\.venueflow\.ie")

@router.post("/sendgrid/inbound", dependencies=[Depends(require_inbound_email_token)])
async def sendgrid_inbound_parse(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives SendGrid Inbound Parse email webhooks.
    
    Parses recipient headers, maps them to a booking ID, and enqueues the quote extractor task.
    """
    form_data = await request.form()
    to_address = form_data.get("to", "")
    email_body = form_data.get("text", "")
    subject = form_data.get("subject", "")
    sender = form_data.get("from", "")

    logger.info(f"SendGrid Inbound Webhook: Received email from {sender} to {to_address} (Subject: {subject})")

    # Match booking ID from 'to' address
    match = BOOKING_EMAIL_RE.search(to_address)
    if not match:
        logger.warning(f"Inbound email to '{to_address}' did not match booking address regex. Ignored.")
        return {"status": "ignored", "reason": "invalid_address"}

    booking_id = match.group(1)
    result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = result.first()
    if not booking:
        logger.warning(f"Inbound email referenced booking {booking_id} which does not exist in database.")
        return {"status": "ignored", "reason": "booking_not_found"}

    # Enqueue the quote extractor task with the raw email body and booking id
    await enqueue_agent_task("quote-extractor", {
        "booking_id": booking.id,
        "email_body": email_body,
        "sender": sender,
        "subject": subject
    })
    
    logger.info(f"SendGrid webhook: enqueued quote-extractor for booking {booking_id}")
    return {"status": "success", "booking_id": booking_id}
