import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.models import User, Wedding, Payment
from app.api.v1.endpoints.auth import get_current_user
from app.utils.tasks import enqueue_agent_task

logger = logging.getLogger(__name__)
router = APIRouter()


async def activate_wedding_planning(db: AsyncSession, wedding: Wedding) -> None:
    """Side-effects of a successful coordinator-fee payment: unlock the full plan.

    The intake_planner already ran for FREE at intake (the preview), so the budget +
    timeline exist. Payment promotes the wedding to 'planning' and runs the paid
    venue + supplier matcher cascade. Shared by the Stripe webhook, the mock
    checkout, and the dev mock endpoint so the trigger lives in exactly one place.
    """
    wedding.status = "planning"
    db.add(wedding)
    await db.commit()
    await enqueue_agent_task("plan-cascade", {"wedding_id": wedding.id})
    logger.info(f"Payment unlocked wedding {wedding.id}; plan-cascade enqueued")


class CheckoutRequest(BaseModel):
    wedding_id: str


@router.post("/checkout")
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Starts the one-time coordinator-fee checkout for a wedding.

    Provider is selected by ``settings.PAYMENTS_PROVIDER``:
      - "mock"  : no real charge. Records a mock Payment row and immediately
                  activates planning. Returns ``{provider, status:"paid", url:null}``.
                  This is the pitch/demo path — free, instant, no Stripe account.
      - "stripe": creates a real Stripe Checkout Session (test or live keys) and
                  returns its hosted ``url`` for the frontend to redirect to. The
                  ``/webhooks/stripe`` handler activates planning on completion.

    Swapping demo -> real payments is a single env change
    (``PAYMENTS_PROVIDER=stripe`` + ``STRIPE_SECRET_KEY``); no code change here.
    """
    result = await db.exec(select(Wedding).where(Wedding.id == payload.wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    if wedding.couple_user_id != current_user.id and wedding.planner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to pay for this wedding")

    amount = settings.COUPLE_PRICE_EUR

    if settings.PAYMENTS_PROVIDER == "stripe":
        return await _stripe_checkout(wedding, amount)

    # --- Mock provider (default): no charge, instant activation ---
    payment = Payment(
        payer_user_id=current_user.id,
        wedding_id=wedding.id,
        amount=amount,
        currency="EUR",
        stripe_payment_id=f"mock_{uuid.uuid4().hex[:16]}",
        status="succeeded",
        payment_type="coordinator_fee",
    )
    db.add(payment)
    await activate_wedding_planning(db, wedding)

    return {
        "provider": "mock",
        "status": "paid",
        "url": None,
        "amount": amount,
        "currency": "EUR",
        "wedding_id": wedding.id,
        "message": "Demo payment recorded (no real charge). AI planning started.",
    }


async def _stripe_checkout(wedding: Wedding, amount: float) -> dict:
    """Creates a real Stripe Checkout Session.

    ``stripe`` is imported lazily so the mock path keeps working even when the
    package isn't installed.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="PAYMENTS_PROVIDER=stripe but STRIPE_SECRET_KEY is not set.",
        )
    try:
        import stripe
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Stripe provider selected but the 'stripe' package is not installed (pip install stripe).",
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY
    success_url = f"{settings.FRONTEND_BASE_URL}/wedding?paid=1"
    cancel_url = f"{settings.FRONTEND_BASE_URL}/wedding/checkout?cancelled=1"

    line_item = (
        {"price": settings.STRIPE_PRICE_ID, "quantity": 1}
        if settings.STRIPE_PRICE_ID
        else {
            "price_data": {
                "currency": "eur",
                "unit_amount": int(amount * 100),
                "product_data": {"name": "VenueFlow AI Wedding Coordinator"},
            },
            "quantity": 1,
        }
    )

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[line_item],
        metadata={"wedding_id": wedding.id},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return {
        "provider": "stripe",
        "status": "redirect",
        "url": session.url,
        "amount": amount,
        "currency": "EUR",
        "wedding_id": wedding.id,
    }
