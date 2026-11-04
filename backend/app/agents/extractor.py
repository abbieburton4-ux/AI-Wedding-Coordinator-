import json
import logging
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import Booking, Wedding, BudgetLine, Quote, AgentDecisionLog, Supplier, Venue
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version

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

    # 2. Fetch budget allocation
    budget_result = await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding_id, BudgetLine.category == category)
    )
    budget_row = budget_result.first()
    allocated_amount = budget_row.allocated_amount if budget_row else 0.0

    # 3. Call Gemini
    client = get_client()
    logger.info(f"Invoking {model} for quote extraction...")
    response = await client.aio.models.generate_content(
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

    # 5b. Roll the quote into the LIVE budget so the couple's Budget page actually
    # moves. MVP model: a category's spent_amount = the latest *available* quote total
    # for that category (the projected spend the couple is tracking). Declined quotes
    # don't count. This is what turns the static budget into a real tracker.
    if is_available and budget_row is not None:
        budget_row.spent_amount = total_amount
        db.add(budget_row)
    
    # 6. Apply Budget Monitor Alert side effect (chain a budget_monitor log if over budget)
    follow_ups = []
    if total_amount > allocated_amount and allocated_amount > 0:
        alert_id = str(uuid.uuid4())
        alert_text = (
            f"Budget alert for category '{category}': quote from {vendor_name} "
            f"(€{total_amount:,.2f}) exceeds allocated budget (€{allocated_amount:,.2f}) "
            f"by €{total_amount - allocated_amount:,.2f}."
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
            input_payload={"allocated": allocated_amount, "quote_total": total_amount},
            output_payload={"alert_message": alert_text, "category": category}
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
