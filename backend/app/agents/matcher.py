import json
import logging
import uuid
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import Wedding, Venue, Supplier, Booking, BudgetLine
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version
from app.utils.constants import region_matches

logger = logging.getLogger(__name__)

# Pydantic Schemas for Gemini Structured Outputs
class MatchDraft(BaseModel):
    vendor_id: str = Field(description="The exact database ID of the venue or supplier.")
    rank: int = Field(description="The rank (1 is best).")
    matching_rationale: str = Field(description="Detailed explanation of why this vendor matches the wedding profile constraints (style, budget, capacity, region).")
    draft_inquiry_email: str = Field(description="A highly personalized, warm, and professional inquiry email draft to send to the vendor.")

class MatchingResult(BaseModel):
    shortlist: list[MatchDraft] = Field(description="List of shortlisted venues/suppliers (up to 3).")
    rationale_summary: str = Field(description="A short summary explaining the recommendation reasoning.")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0).")


VENUE_SYSTEM_INSTRUCTION = (
    "You are an expert Irish wedding coordinator agent called venue_matcher. Your job is to match the couple's "
    "wedding profile with available venues in the database.\n\n"
    "MATCHING CRITERIA:\n"
    "1. Capacity: Venue max capacity must be >= couple's guest estimate, and min capacity must be <= guest estimate.\n"
    "2. Region: Prioritize venues in the preferred region. If no venues in the region fit the guest count/budget, "
    "you MUST suggest venues in adjacent regions, noting this clearly in your rationale. Never suggest hallucinated venues.\n"
    "3. Budget: Match the estimated cost (rental + food per head * guests) against the allocated venue budget.\n"
    "4. Style: Match the couple's style notes (e.g. gothic castle, rustic, eco-friendly) with venue types.\n\n"
    "OUTPUT REQUIREMENT:\n"
    "- Return a ranked shortlist of up to 3 venues.\n"
    "- For each, write a matching_rationale highlighting trade-offs.\n"
    "- Write a personalized draft_inquiry_email from the couple asking for a brochure and availability. "
    "Use the venue's email or general tone. Mention their specific wedding date or date range.\n"
    "Return valid JSON conforming to the response schema."
)

SUPPLIER_SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are an expert Irish wedding coordinator agent called supplier_matcher. Your job is to match the couple's "
    "wedding profile with available suppliers in the category: '{category}'.\n\n"
    "MATCHING CRITERIA:\n"
    "1. Region: Prioritize suppliers located in or servicing the preferred region.\n"
    "2. Budget: Verify if their standard package prices fit within the allocated category budget. "
    "For photographers/music, this is package cost. For catering, check per head cost.\n"
    "3. Style: Match the couple's style notes (e.g. documentary photo, wildflower arrangements) with supplier attributes.\n\n"
    "OUTPUT REQUIREMENT:\n"
    "- Return a ranked shortlist of up to 3 suppliers.\n"
    "- For each, write a matching_rationale.\n"
    "- Write a personalized draft_inquiry_email from the couple asking for pricing and availability on their wedding date.\n"
    "Return valid JSON conforming to the response schema."
)


@run_agent("venue_matcher", "venue_match")
async def run_venue_matcher(db: AsyncSession, wedding_id: str):
    """Matches available venues against the wedding profile and creates shortlisted bookings."""
    agent_id = "venue_matcher"
    model = model_for(agent_id)
    prompt_version = get_prompt_version(VENUE_SYSTEM_INSTRUCTION)
    
    # 1. Fetch wedding context
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise ValueError(f"Wedding not found: {wedding_id}")
        
    # Get budget allocation for venue
    budget_result = await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding_id, BudgetLine.category == "venue")
    )
    venue_budget_row = budget_result.first()
    venue_budget = venue_budget_row.allocated_amount if venue_budget_row else wedding.budget_total * 0.4
    
    guest_count = wedding.guest_count_estimate
    preferred_region = wedding.region
    
    # 2. Fetch and pre-filter candidate venues by capacity
    all_venues_result = await db.exec(select(Venue))
    all_venues = all_venues_result.all()
    
    venues_by_capacity = [
        v for v in all_venues
        if (v.capacity_min is None or v.capacity_min <= guest_count) and
           (v.capacity_max is None or v.capacity_max >= guest_count)
    ]
    
    # Prioritize preferred region
    venues_in_region = [v for v in venues_by_capacity if region_matches(v.region, preferred_region)]
    
    if len(venues_in_region) >= 3:
        filtered_venues = venues_in_region
    else:
        # Fallback to venues outside region
        other_venues = [v for v in venues_by_capacity if not region_matches(v.region, preferred_region)]
        filtered_venues = venues_in_region + other_venues[:(3 - len(venues_in_region))]
        
    # 3. Formulate input context
    input_payload = {
        "wedding_profile": {
            "guest_count": guest_count,
            "region_preference": preferred_region,
            "venues_matching_region_count": len(venues_in_region),
            "allocated_venue_budget": venue_budget,
            "style_notes": wedding.style_notes,
            "ceremony_type": wedding.ceremony_type
        },
        "available_venues": [
            {
                "id": v.id,
                "name": v.name,
                "address": v.address,
                "region": v.region,
                "type": v.venue_type,
                "capacity": {"min": v.capacity_min, "max": v.capacity_max},
                "accommodation": v.on_site_accommodation,
                "pricing": v.pricing_summary
            } for v in filtered_venues
        ]
    }
    
    client = get_client()
    prompt = f"Match venues for the following couple profile and options:\n{json.dumps(input_payload, indent=2)}"
    
    # Call Gemini
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=VENUE_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=MatchingResult,
            temperature=0.2
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
    
    # 4. Check for hallucinated IDs
    valid_venue_ids = {v.id for v in filtered_venues}
    hallucinated_ids = [
        match["vendor_id"] for match in result_dict.get("shortlist", [])
        if match["vendor_id"] not in valid_venue_ids
    ]
    
    if hallucinated_ids:
        return (
            {
                "status": "blocked",
                "error_kind": "hallucination_guardrail",
                "warning": f"Agent suggested hallucinated venue IDs: {hallucinated_ids}",
                "rationale_summary": "Venue matcher blocked: agent fabricated venue IDs."
            },
            result_dict.get("confidence_score", 0.0),
            model,
            prompt_version,
            api_calls
        )
        
    # 5. Success Path: Insert shortlisted Bookings
    for match in result_dict.get("shortlist", []):
        v_id = match["vendor_id"]
        # Avoid duplicate bookings
        dup_result = await db.exec(
            select(Booking).where(Booking.wedding_id == wedding.id, Booking.venue_id == v_id)
        )
        if not dup_result.first():
            booking = Booking(
                id=f"bkv_{uuid.uuid4().hex[:10]}",
                wedding_id=wedding.id,
                venue_id=v_id,
                status="shortlisted",
                sourced_by_agent_id="venue_matcher"
            )
            db.add(booking)
            
    return (
        result_dict,
        result_dict.get("confidence_score", 1.0),
        model,
        prompt_version,
        api_calls
    )


@run_agent("supplier_matcher", "supplier_match")
async def run_supplier_matcher(db: AsyncSession, wedding_id: str, category: str):
    """Matches available suppliers for a specific category against the wedding profile."""
    agent_id = "supplier_matcher"
    model = model_for(agent_id)
    system_instruction = SUPPLIER_SYSTEM_INSTRUCTION_TEMPLATE.format(category=category)
    prompt_version = get_prompt_version(system_instruction)
    
    # 1. Fetch wedding context
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise ValueError(f"Wedding not found: {wedding_id}")
        
    # Get budget allocation for category
    budget_result = await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding_id, BudgetLine.category == category)
    )
    cat_budget_row = budget_result.first()
    cat_budget = cat_budget_row.allocated_amount if cat_budget_row else wedding.budget_total * 0.1
    
    guest_count = wedding.guest_count_estimate
    preferred_region = wedding.region
    
    # 2. Fetch candidate suppliers by category
    all_suppliers_result = await db.exec(
        select(Supplier).where(Supplier.category == category)
    )
    all_suppliers = all_suppliers_result.all()
    
    # Prioritize suppliers servicing/in preferred region
    suppliers_in_region = [s for s in all_suppliers if region_matches(s.location, preferred_region)]
    if len(suppliers_in_region) >= 3:
        filtered_suppliers = suppliers_in_region
    else:
        other_suppliers = [s for s in all_suppliers if not region_matches(s.location, preferred_region)]
        filtered_suppliers = suppliers_in_region + other_suppliers[:(3 - len(suppliers_in_region))]
        
    # 3. Formulate input context
    input_payload = {
        "wedding_profile": {
            "guest_count": guest_count,
            "region_preference": preferred_region,
            "suppliers_matching_region_count": len(suppliers_in_region),
            "allocated_category_budget": cat_budget,
            "style_notes": wedding.style_notes,
            "ceremony_type": wedding.ceremony_type
        },
        "available_suppliers": [
            {
                "id": s.id,
                "name": s.name,
                "location": s.location,
                "contact_info": s.contact_info,
                "pricing": s.pricing_summary,
                "attributes": s.attributes
            } for s in filtered_suppliers
        ]
    }
    
    client = get_client()
    prompt = f"Match suppliers in category '{category}' for the following profile:\n{json.dumps(input_payload, indent=2)}"
    
    # Call Gemini
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=MatchingResult,
            temperature=0.2
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
    
    # 4. Check for hallucinated IDs
    valid_supplier_ids = {s.id for s in filtered_suppliers}
    hallucinated_ids = [
        match["vendor_id"] for match in result_dict.get("shortlist", [])
        if match["vendor_id"] not in valid_supplier_ids
    ]
    
    if hallucinated_ids:
        return (
            {
                "status": "blocked",
                "error_kind": "hallucination_guardrail",
                "warning": f"Agent suggested hallucinated supplier IDs: {hallucinated_ids}",
                "rationale_summary": f"Supplier matcher blocked: agent fabricated {category} IDs."
            },
            result_dict.get("confidence_score", 0.0),
            model,
            prompt_version,
            api_calls
        )
        
    # 5. Success Path: Insert shortlisted Bookings
    for match in result_dict.get("shortlist", []):
        s_id = match["vendor_id"]
        # Avoid duplicate bookings
        dup_result = await db.exec(
            select(Booking).where(Booking.wedding_id == wedding.id, Booking.supplier_id == s_id)
        )
        if not dup_result.first():
            booking = Booking(
                id=f"bks_{uuid.uuid4().hex[:10]}",
                wedding_id=wedding.id,
                supplier_id=s_id,
                status="shortlisted",
                sourced_by_agent_id="supplier_matcher"
            )
            db.add(booking)
            
    return (
        result_dict,
        result_dict.get("confidence_score", 1.0),
        model,
        prompt_version,
        api_calls
    )
