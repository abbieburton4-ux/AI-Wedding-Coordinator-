import re
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import Wedding, Booking
from app.utils.tasks import enqueue_agent_task
from app.api.v1.internal import require_inbound_email_token
from app.api.v1.endpoints.payments import activate_wedding_planning

logger = logging.getLogger(__name__)
router = APIRouter()

# Regex to capture booking ID from recipient: booking-<id>@inbox.venueflow.ie
BOOKING_EMAIL_RE = re.compile(r"booking-([a-zA-Z0-9_]+)@inbox\.venueflow\.ie")

@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives Stripe Checkout & Billing webhook events.
    
    Marks weddings as 'planning' when payment succeeds and enqueues the intake planner task.
    """
    if settings.DEVELOPMENT_MODE:
        payload = await request.json()
    else:
        # Outside dev, only a correctly signed Stripe event is accepted.
        if settings.PAYMENTS_PROVIDER != "stripe" or not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")
        import stripe  # lazy: only installed/needed for real Stripe
        try:
            event = stripe.Webhook.construct_event(
                await request.body(),
                request.headers.get("stripe-signature", ""),
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")
        payload = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    event_type = payload.get("type")
    
    logger.info(f"Stripe Webhook received event: {event_type}")
    
    if event_type == "checkout.session.completed":
        session = payload.get("data", {}).get("object", {})
        metadata = session.get("metadata", {})
        wedding_id = metadata.get("wedding_id")
        
        if wedding_id:
            result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
            wedding = result.first()
            if wedding:
                await activate_wedding_planning(db, wedding)
                return {"status": "success", "message": f"Wedding {wedding_id} updated to planning."}
            else:
                logger.error(f"Stripe webhook: wedding {wedding_id} not found in database.")
        else:
            logger.error("Stripe webhook: checkout.session.completed did not contain wedding_id in metadata.")
            
    return {"status": "ignored"}


@router.post("/debug/stripe-mock")
async def debug_stripe_mock(wedding_id: str, db: AsyncSession = Depends(get_db)):
    """Mock endpoint to simulate a successful Stripe payment for local testing."""
    if not settings.DEVELOPMENT_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock endpoints are only available in development mode."
        )
        
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wedding {wedding_id} not found."
        )
        
    # Trigger same side-effects as a completed Stripe payment.
    await activate_wedding_planning(db, wedding)

    return {
        "status": "mocked", 
        "wedding_id": wedding_id, 
        "new_status": wedding.status,
        "message": "Enqueued intake-planner task successfully."
    }


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
