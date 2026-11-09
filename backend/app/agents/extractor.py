import json
import logging
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import (
    AgentDecisionLog, Booking, BudgetCategory, CoupleVendor, CoupleVendorQuote, Quote, Supplier,
    Venue,
)
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version
from app.agents.privacy import send_prompt
from app.utils.budget_compare import compare_quote
from app.utils.budget_math import format_cents

logger = logging.getLogger(__name__)

# Pydantic Schemas for Gemini Structured Outputs
class QuoteLineItem(BaseModel):
    item: str = Field(description="The name of the quote item (e.g. Venue rental, Evening buffet).")
    description: str = Field(description="Details or inclusions.")
    amount: float = Field(description="Price for this line item.")

class QuoteResult(BaseModel):
    is_available: bool = Field(description="Whether the supplier explicitly confirmed availability for the wedding date in the email.")
    line_items: list[QuoteLineItem] = Field(description="List of priced items extracted from the email.")
    total_amount: float = Field(description="Total quote amount extracted.")
    currency: str = Field(default="EUR", description="Currency code (e.g. EUR).")
    rationale_text: str = Field(description="Structured explanation of the quote and any notable terms (e.g., corkage fees, deposit requirements).")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0).")


SYSTEM_INSTRUCTION = (
    "You are a helpful Irish wedding coordinator agent called quote_extractor. Your job is to extract structured "
    "pricing, availability, and itemized details from a vendor's email reply.\n\n"
    "EXTRACTION RULES:\n"
    "1. Availability: Mark is_available=true if they explicitly state they are free on the date/range, or imply it by sending a quote. "
    "Mark false if they state they are fully booked.\n"
    "2. Line Items: Extract each priced item clearly (e.g. Venue hire, catering per head, service charge, ceremony music). "
    "Normalize descriptions and capture individual amounts.\n"
    "3. Total Amount: Calculate the exact total price offered. If they charge per-head, multiply by the guest count if guest count is mentioned "
    "(otherwise sum the static fees and note it in rationales).\n"
    "4. Currency: Set default to EUR unless stated otherwise.\n\n"
    "Return valid JSON conforming to the response schema."
)


async def _resolve_quote_extract_parent(db: AsyncSession, booking_id: str) -> Optional[str]:
    """Finds parent agent decision log to link matching -> inquiry -> extraction."""
    # 1. Most recent successful inquiry_send
    result = await db.exec(
        select(AgentDecisionLog)
        .where(AgentDecisionLog.booking_id == booking_id, 
               AgentDecisionLog.decision_type == "inquiry_send", 
               AgentDecisionLog.status == "success")
        .order_by(AgentDecisionLog.timestamp.desc())
    )
    row = result.first()
    if row:
        return str(row.id)

    # 2. Or bookings.sourced_by_agent_id
    booking_result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = booking_result.first()
    if booking and booking.sourced_by_agent_id:
        # Confirm it points to a real log row
        log_check = await db.exec(select(AgentDecisionLog).where(AgentDecisionLog.id == booking.sourced_by_agent_id))
        if log_check.first():
            return booking.sourced_by_agent_id

    return None


@run_agent("quote_extractor", "quote_draft")
async def run_quote_extractor(db: AsyncSession, wedding_id: str, booking_id: str, email_body: str):
    """Parses supplier email body, extracts structured quote, updates booking status and logs budget alerts."""
    agent_id = "quote_extractor"
    model = model_for(agent_id)
    prompt_version = get_prompt_version(SYSTEM_INSTRUCTION)
    
    # 1. Fetch Booking and context
    result = await db.exec(select(Booking).where(Booking.id == booking_id))
    booking = result.first()
    if not booking:
        raise ValueError(f"Booking not found: {booking_id}")
        
    if booking.supplier_id:
        supplier_result = await db.exec(select(Supplier).where(Supplier.id == booking.supplier_id))
        supplier = supplier_result.first()
        if not supplier:
            raise ValueError(f"Supplier not found for ID: {booking.supplier_id}")
        category = supplier.category
        vendor_name = supplier.name
    elif booking.venue_id:
        venue_result = await db.exec(select(Venue).where(Venue.id == booking.venue_id))
        venue = venue_result.first()
        if not venue:
            raise ValueError(f"Venue not found for ID: {booking.venue_id}")
        category = "venue"
        vendor_name = venue.name
    else:
        raise ValueError(f"Booking {booking_id} has neither supplier_id nor venue_id.")

    # 2. The couple's own budget categories (PD-004), to compare the quote with.
    budget_categories = (await db.exec(
        select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id)
        .order_by(BudgetCategory.created_at, BudgetCategory.id)
    )).all()

    # 3. Call Gemini
    client = get_client()
    logger.info(f"Invoking {model} for quote extraction...")
    response = await send_prompt(
        db, wedding_id, client,
        model=model,
        contents=email_body,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=QuoteResult,
            temperature=0.1
        )
    )
    
    result_dict = json.loads(response.text)
    
    # Track API metrics
    usage = response.usage_metadata
    api_calls = [{
        "provider": "google",
        "model": model,
        "tokens": {
            "input": usage.prompt_token_count if usage else 0,
            "output": usage.candidates_token_count if usage else 0
        }
    }]
    
    total_amount = result_dict.get("total_amount", 0.0)
    is_available = result_dict.get("is_available", True)
    line_items = result_dict.get("line_items", [])
    
    # 4. Save Quote
    quote = Quote(
        id=f"q_{uuid.uuid4().hex[:10]}",
        booking_id=booking_id,
        line_items=line_items,
        total_amount=total_amount,
        currency=result_dict.get("currency", "EUR"),
        status="pending",
        generated_by_agent_id=agent_id,
        rationale_text=result_dict.get("rationale_text")
    )
    db.add(quote)
    
    # 5. Transition Booking Status
    booking.status = "quoted" if is_available else "declined"
    db.add(booking)

    # The quote is never written into the couple's budget: its figures come from what
    # the couple enter, and only they record a cost (PD-013, rule 4).

    # 6. Budget alert (a budget_monitor log row) when an available quote is over the
    # planned amount of the matching budget category. The same comparison as the
    # vendor cards (B42): US dollars only, otherwise no alert rather than a guessed one.
    follow_ups = []
    check = compare_quote(total_amount, result_dict.get("currency"), category,
                          budget_categories)
    if is_available and check["budget_comparison"] == "over":
        alert_id = str(uuid.uuid4())
        planned_cents = check["planned_cents"]
        quote_cents = planned_cents + check["over_by_cents"]
        alert_text = (
            f"Budget alert for {check['budget_category_name']}: the quote from "
            f"{vendor_name} ({format_cents(quote_cents)}) exceeds what you planned "
            f"({format_cents(planned_cents)}) by {format_cents(check['over_by_cents'])}."
        )

        # Insert budget_monitor audit log row directly
        alert_log = AgentDecisionLog(
            id=alert_id,
            agent_id="budget_monitor",
            model_id=model,
            prompt_version=prompt_version,
            wedding_id=wedding_id,
            booking_id=booking_id,
            parent_decision_id=None,  # Will link after parent log is committed
            trigger="parent_decision",
            decision_type="budget_alert",
            status="success",
            rationale_summary=alert_text,
            input_payload={"planned_cents": planned_cents, "quote_cents": quote_cents},
            output_payload={"alert_message": alert_text, "category": category,
                            "budget_category": check["budget_category_name"]}
        )
        db.add(alert_log)
        
        follow_ups.append({
            "decision_id": alert_id,
            "agent_id": "budget_monitor",
            "decision_type": "budget_alert"
        })

    # Return structured results.
    # The orchestrator will fetch the parent_decision_id using the custom kwargs logic
    # and update the parent_decision_id on the committed main log.
    return (
        result_dict,
        result_dict.get("confidence_score"),
        model,
        prompt_version,
        api_calls,
        follow_ups
    )


# --- A reply to one of the couple's own vendors (PD-012, B62) ---

class VendorReplyLineItem(BaseModel):
    item: str = Field(description="What is priced (e.g. Venue rental, Dinner per guest).")
    amount: Optional[float] = Field(
        default=None, description="Price for this item as written in the reply, or null.")


class VendorReplyResult(BaseModel):
    is_available: Optional[bool] = Field(
        default=None,
        description="True if the vendor says they're free on the date, false if they say "
                    "they're booked or unavailable, null if the reply doesn't say.")
    line_items: list[VendorReplyLineItem] = Field(
        default_factory=list, description="Each priced item the reply lists.")
    total_amount: Optional[float] = Field(
        default=None, description="The total price the reply offers, or null if it gives none.")
    currency: Optional[str] = Field(
        default=None,
        description="ISO currency code written or shown in the reply (e.g. USD), or null "
                    "if the reply doesn't make it clear.")
    summary: str = Field(
        description="Two or three plain sentences on the price and any terms worth "
                    "noticing (deposit, minimums, service charges, what's not included).")
    confidence_score: Optional[float] = Field(
        default=None, description="Your confidence in this reading, 0.0 to 1.0.")


VENDOR_REPLY_INSTRUCTION = (
    "You read a wedding vendor's email reply that the couple pasted in, and report what "
    "it says about price and availability. Report only what the reply states: never "
    "guess a price, a currency or availability, and leave a field null when the reply "
    "doesn't give it. If the price is per guest and the reply states the guest count, "
    "give the total and say how you worked it out in the summary; otherwise give no "
    "total. Return JSON matching the response schema."
)

# A reply quoting more than this for one vendor is far more likely a misreading.
MAX_REPLY_CENTS = 100_000_000  # 1,000,000.00
_CURRENCY = re.compile(r"^[A-Z]{3}$")


def to_cents(value) -> Optional[int]:
    """A model-given amount as whole cents, or None if it isn't a usable number."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@run_agent("quote_extractor", "quote_draft")
async def run_vendor_reply_reader(db: AsyncSession, wedding_id: str, email_body: str,
                                  vendor_id: str):
    """Reads the price and availability from a reply to one of the couple's vendors.

    Only the pasted text goes to the AI: none of the vendor's saved details do, and
    their contact person, email and phone are removed from the text along with the
    party's (``privacy.load_personal_terms``). The result is saved as the AI's reading.
    It never changes the vendor's status or the budget; the couple do that (rule 4).
    """
    model = model_for("quote_extractor")
    prompt_version = get_prompt_version(VENDOR_REPLY_INSTRUCTION)

    vendor = (await db.exec(select(CoupleVendor).where(
        CoupleVendor.id == vendor_id, CoupleVendor.wedding_id == wedding_id))).first()
    if not vendor:
        raise ValueError("That vendor isn't on this wedding's list.")

    response = await send_prompt(
        db, wedding_id, get_client(),
        model=model,
        contents=email_body,
        config=types.GenerateContentConfig(
            system_instruction=VENDOR_REPLY_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=VendorReplyResult,
            temperature=0.1,
        ),
    )
    reply = json.loads(response.text)
    if not isinstance(reply, dict):
        reply = {}
    usage = response.usage_metadata
    tokens = ((usage.prompt_token_count, usage.candidates_token_count) if usage
              else (None, None))
    api_calls = [{"provider": "google", "model": model,
                  "tokens": {"input": tokens[0], "output": tokens[1]}}]
    confidence = reply.get("confidence_score")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = None

    def blocked(kind: str, warning: str):
        out = {"status": "blocked", "error_kind": kind, "warning": warning,
               "vendor_id": vendor_id}
        return out, confidence, model, prompt_version, api_calls, [], tokens

    raw_total = reply.get("total_amount")
    total_cents = to_cents(raw_total) if raw_total is not None else None
    if raw_total is not None and (total_cents is None or total_cents < 0
                                  or total_cents > MAX_REPLY_CENTS):
        return blocked("implausible_total",
                       "The price the AI read doesn't look right, so nothing was saved. "
                       "Check the reply yourself.")
    available = reply.get("is_available")
    if not isinstance(available, bool):
        available = None
    if total_cents is None and available is None:
        return blocked("nothing_found",
                       "The AI found no price or availability in that reply, so nothing "
                       "was saved.")

    currency = reply.get("currency")
    currency = currency.strip().upper() if isinstance(currency, str) else None
    if not currency or not _CURRENCY.match(currency):
        currency = None
    items = []
    for li in reply.get("line_items") or []:
        if not isinstance(li, dict) or not isinstance(li.get("item"), str):
            continue
        cents = to_cents(li.get("amount")) if li.get("amount") is not None else None
        if cents is not None and not 0 <= cents <= MAX_REPLY_CENTS:
            cents = None
        items.append({"item": li["item"].strip()[:200], "amount_cents": cents})
    summary = reply.get("summary") if isinstance(reply.get("summary"), str) else None

    db.add(CoupleVendorQuote(
        vendor_id=vendor.id, total_cents=total_cents, currency=currency,
        is_available=available, line_items=items[:50],
        summary=summary.strip()[:2000] if summary else None,
    ))
    result = {
        "status": "success",
        "vendor_id": vendor_id,
        "total_cents": total_cents,
        "currency": currency,
        "is_available": available,
        "line_items": items[:50],
        "rationale_summary": "Read a vendor's reply: "
        + ("a total" if total_cents is not None else "no total")
        + ("; availability stated" if available is not None else ""),
    }
    return result, confidence, model, prompt_version, api_calls, [], tokens
