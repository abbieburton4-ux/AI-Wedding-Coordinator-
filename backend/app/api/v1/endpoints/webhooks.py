import re
import logging
from fastapi import APIRouter, Depends, Request
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import Booking
from app.api.v1.internal import require_inbound_email_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Regex to capture booking ID from recipient: booking-<id>@inbox.venueflow.ie
BOOKING_EMAIL_RE = re.compile(r"booking-([a-zA-Z0-9_]+)@inbox\.venueflow\.ie")

@router.post("/sendgrid/inbound", dependencies=[Depends(require_inbound_email_token)])
async def sendgrid_inbound_parse(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives SendGrid Inbound Parse email webhooks.
    
    Parses recipient headers and maps them to a booking ID. It never runs the quote
    extractor: that sends the email to the AI, which needs a person to check the text
    first (PD-008). Nothing is stored, so the email itself isn't kept.
    """
    form_data = await request.form()
    to_address = form_data.get("to", "")

    # Sender, subject and body can name the couple or guests, so they stay out of the logs.
    logger.info("SendGrid Inbound Webhook: received an email")

    # Match booking ID from 'to' address
    match = BOOKING_EMAIL_RE.search(to_address)
    if not match:
        logger.warning("Inbound email address did not match a booking. Ignored.")
        return {"status": "ignored", "reason": "invalid_address"}

    booking_id = match.group(1)
    result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = result.first()
    if not booking:
        logger.warning(f"Inbound email referenced booking {booking_id} which does not exist in database.")
        return {"status": "ignored", "reason": "booking_not_found"}

    # Nothing goes to the AI without a person checking the text first (PD-008), and
    # no one is watching this path, so the email isn't sent to the quote extractor.
    # The couple paste the vendor's reply on the Vendors screen instead.
    logger.info(f"SendGrid webhook: email for booking {booking_id} not sent to the AI")
    return {"status": "not_processed", "booking_id": booking_id, "reason": "needs_review"}
