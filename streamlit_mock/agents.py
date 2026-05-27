import json
import uuid
import time
import os
import hashlib
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
import db

# Pydantic schemas for Structured Outputs

# Re-export shared category constants so existing callers (app.py imports
# agents.SUPPLIER_CATEGORIES) keep working. New code should import from
# constants.py directly.
from constants import (
    ALLOWED_BUDGET_CATEGORIES,
    SUPPLIER_CATEGORIES,
    region_matches,
    normalize_category as _normalize_category,
)

class BudgetLineDraft(BaseModel):
    category: str = Field(description=f"Must be one of: {', '.join(sorted(ALLOWED_BUDGET_CATEGORIES))}")
    allocated_amount: float = Field(description="Amount allocated in EUR")
    rationale: str = Field(description="Brief explanation of why this amount was allocated")

class TimelineItemDraft(BaseModel):
    title: str = Field(description="Short milestone title")
    description: str = Field(description="Brief description of what to do")
    months_before: float = Field(description="Due date as number of months before the wedding date (e.g., 12.0 for 1 year, 0.5 for 2 weeks, 0.0 for wedding day)")
    kind: str = Field(description="Must be 'planning' or 'day_of'")

class IntakeResult(BaseModel):
    is_budget_realistic: bool = Field(description="False if the budget is clearly too low for the estimated guest count in that Irish region (e.g., €5,000 for 150 guests in Dublin). True otherwise.")
    guardrail_warning: str = Field(description="Reason why the budget is unrealistic (with Irish market-rate comparisons), or empty if realistic.")
    budget_lines: list[BudgetLineDraft] = Field(description="Allocated budget split across categories.")
    timeline_items: list[TimelineItemDraft] = Field(description="Timeline planning milestones.")
    rationale_summary: str = Field(description="A short summary of the generated plan or guardrail violation.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 representing the agent's confidence.")

class MatchDraft(BaseModel):
    vendor_id: str = Field(description="The exact database ID of the venue or supplier.")
    rank: int = Field(description="The rank (1 is best).")
    matching_rationale: str = Field(description="Detailed explanation of why this vendor matches the wedding profile constraints (style, budget, capacity, region).")
    draft_inquiry_email: str = Field(description="A highly personalized, warm, and professional inquiry email draft to send to the vendor.")

class MatchingResult(BaseModel):
    shortlist: list[MatchDraft] = Field(description="List of shortlisted venues/suppliers (up to 3).")
    rationale_summary: str = Field(description="A short summary explaining the recommendation reasoning.")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0).")

class QuoteLineItem(BaseModel):
    item: str = Field(description="The name of the quote item (e.g., Venue rental, Evening buffet).")
    description: str = Field(description="Details or inclusions.")
    amount: float = Field(description="Price for this line item.")

class QuoteResult(BaseModel):
    is_available: bool = Field(description="Whether the supplier explicitly confirmed availability for the wedding date in the email.")
    line_items: list[QuoteLineItem] = Field(description="List of priced items extracted from the email.")
    total_amount: float = Field(description="Total quote amount extracted.")
    currency: str = Field(default="EUR", description="Currency code (e.g. EUR).")
    rationale_text: str = Field(description="Structured explanation of the quote and any notable terms (e.g., corkage fees, deposit requirements).")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0).")


# API Setup & Model Resolver Helpers

def get_client(api_key=None):
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API key not found. Please set the GEMINI_API_KEY environment variable or enter it in the settings sidebar.")
    return genai.Client(api_key=key, http_options={"timeout": 30.0})

def model_for(agent_name: str) -> str:
    """Returns the targeted Gemini model for an agent (Pro for reasoning, Flash for extraction)."""
    if agent_name in ("intake_planner", "venue_matcher", "supplier_matcher"):
        return "gemini-2.5-pro"
    return "gemini-2.5-flash"

def get_prompt_version(system_instruction: str) -> str:
    """Generates a stable prompt version hash from the system instruction text."""
    sha = hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()[:8]
    return f"v1.0-{sha}"


def _assert_wedding_exists(conn, cursor, wedding_id):
    """Raise ValueError immediately if the wedding doesn't exist, before any
    audit log row is opened. Mirrors the pattern quote_extractor uses for
    bookings — no FK surprise on the pending-log INSERT, no orphan log rows,
    a clear ValueError that the caller can handle distinctly from a Gemini
    failure."""
    cursor.execute("SELECT 1 FROM weddings WHERE id = ?", (wedding_id,))
    if cursor.fetchone() is None:
        conn.close()
        raise ValueError(f"Wedding not found: {wedding_id!r}")


def log_user_action(
    cursor,
    *,
    wedding_id,
    decision_type,
    rationale_summary,
    booking_id=None,
    parent_decision_id=None,
    user_id=None,
    trigger="couple_action",
    status="success",
    overridden_by_user_id=None,
):
    """Write a non-LLM audit log row for a user/system action (inquiry_send,
    quote_accept, etc.). Returns the new log row's id.

    Caller owns the surrounding transaction — this helper does not commit.
    That lets the caller bundle related domain mutations (booking status
    flip, payment row, etc.) and the audit row in one atomic write."""
    log_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO agent_decision_logs (
            id, agent_id, wedding_id, user_id, booking_id, parent_decision_id,
            trigger, decision_type, status, rationale_summary,
            overridden_by_user_id, external_api_calls
        )
        VALUES (?, 'system', ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')
    """, (
        log_id, wedding_id, user_id, booking_id, parent_decision_id,
        trigger, decision_type, status, rationale_summary,
        overridden_by_user_id,
    ))
    return log_id


def log_user_override(
    cursor,
    *,
    parent_decision_id,
    overridden_by_user_id,
    wedding_id,
    rationale_summary,
    booking_id=None,
):
    """Record a user override of an AI decision: marks the parent log row
    as overridden AND inserts an override_option child log. Two writes in
    one helper so the audit pair stays consistent — every override has
    both an overridden_by_user_id on the parent and a dedicated row
    capturing the reason."""
    cursor.execute(
        "UPDATE agent_decision_logs SET overridden_by_user_id = ? WHERE id = ?",
        (overridden_by_user_id, parent_decision_id),
    )
    return log_user_action(
        cursor,
        wedding_id=wedding_id,
        booking_id=booking_id,
        decision_type="override_option",
        rationale_summary=rationale_summary,
        parent_decision_id=parent_decision_id,
        user_id=overridden_by_user_id,
        overridden_by_user_id=overridden_by_user_id,
    )


def _resolve_quote_accept_parent(cursor, booking_id):
    """Find the quote_draft log row whose output the user is now accepting.
    Mirrors _resolve_quote_extract_parent: prefers the most recent successful
    quote_draft for this booking. Returns None if none exists (e.g. caller
    accepted a manually-inserted quote)."""
    cursor.execute("""
        SELECT id FROM agent_decision_logs
        WHERE booking_id = ? AND decision_type = 'quote_draft' AND status = 'success'
        ORDER BY timestamp DESC
        LIMIT 1
    """, (booking_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def _resolve_quote_extract_parent(cursor, booking_id):
    """Find the parent agent_decision_log row for a quote_extract decision so
    a judge can trace the full chain: matcher → inquiry_send → quote_extract.

    Preference order:
      1. Most recent successful `inquiry_send` log for this booking — that's
         the action that produced the supplier reply we're now parsing.
      2. The matcher decision that originally sourced the booking, via
         bookings.sourced_by_agent_id.
      3. None — chain breaks here, but only when neither anchor exists
         (e.g. a booking inserted by seed data or a manual test).
    """
    cursor.execute("""
        SELECT id FROM agent_decision_logs
        WHERE booking_id = ? AND decision_type = 'inquiry_send' AND status = 'success'
        ORDER BY timestamp DESC
        LIMIT 1
    """, (booking_id,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("SELECT sourced_by_agent_id FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    if row and row[0]:
        # Confirm the sourced_by_agent_id actually points at a real log row.
        # Old seed data stored an agent name string here ('supplier_matcher')
        # rather than a uuid — those won't resolve and we'd rather return
        # None than write a dangling foreign key.
        cursor.execute("SELECT 1 FROM agent_decision_logs WHERE id = ?", (row[0],))
        if cursor.fetchone():
            return row[0]

    return None


# AGENT IMPLEMENTATIONS

def run_intake_planner(wedding_id, user_id=None, api_key=None, model_name=None):
    """
    Analyzes wedding profile, runs budget realism guardrail, and seeds timeline/budget.
    """
    agent_id = "intake_planner"
    model = model_name or model_for(agent_id)
    decision_id = str(uuid.uuid4())
    start_time = time.time()
    
    system_instruction = (
        "You are an expert Irish wedding coordinator. Your job is to draft a comprehensive budget allocation "
        "and planning timeline for a couple based on their intake form. You must validate if their budget is realistic.\n\n"
        "IRISH MARKET RULES & BUDGET TARGETS:\n"
        "- A typical wedding in Ireland has a total budget of €25,000 to €45,000 for 120-180 guests.\n"
        "- Average cost per head for hotel/catering is €75-€120.\n"
        "- Photographer prices range from €1,500 to €3,500.\n"
        "- Florist prices range from €1,000 to €2,500.\n"
        "- Band & DJ ranges from €2,000 to €3,000.\n"
        "- If a couple proposes a budget that is mathematically impossible (e.g., €5,000 for 150 guests in Dublin, "
        "where catering alone would exceed €12,000), you MUST trigger a budget guardrail warning by setting "
        "is_budget_realistic=false and writing a helpful guardrail_warning explaining the market averages in Ireland.\n\n"
        "CEREMONY BUDGET SPLITS:\n"
        "- 'Irish Catholic': Seed budget lines including a church donation/fee (~€400-500) and standard allocations. "
        "Timeline must include the mandatory pre-marriage course (Accord) at least 6 months before.\n"
        "- 'Civil/Humanist': Seed budget lines with an officiant fee (~€350-450) and omit church donation. "
        "Timeline must include booking the HSE registry appointment (requires 3 months notice minimum in Ireland).\n"
        "- 'Hindu': Seed splits with decoration/mandap and multi-day elements (Mehndi, Sangeet) taking a higher split (~12% on decor/florals, 10% on pre-wedding events).\n"
        "- 'Multi-cultural': Merge Catholic/Hindu or Civil/Hindu elements and explain in rationales.\n\n"
        "TIMELINE HORIZONS:\n"
        "- If the wedding is <6 months away, generate an accelerated 'sprint' timeline (marking early tasks as high priority).\n"
        "- If the wedding date is TBD (date is null, but range is given), write timeline descriptions that adapt (e.g. 'Book venue - 12 months before target range').\n"
        "Return valid JSON conforming to the response schema."
    )
    prompt_version = get_prompt_version(system_instruction)
    
    # 1. Initialize Log
    conn = db.get_connection()
    cursor = conn.cursor()
    # B1: validate wedding exists before opening the pending log row, so a
    # bogus wedding_id raises ValueError cleanly instead of an FK violation.
    _assert_wedding_exists(conn, cursor, wedding_id)
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, model_id, prompt_version, wedding_id, user_id, trigger, decision_type, status)
        VALUES (?, ?, ?, ?, ?, ?, 'couple_action', 'timeline_generate', 'pending')
    """, (decision_id, agent_id, model, prompt_version, wedding_id, user_id))
    conn.commit()

    try:
        # Get Wedding details
        cursor.execute("SELECT * FROM weddings WHERE id = ?", (wedding_id,))
        wedding = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM users WHERE id = ?", (wedding["couple_user_id"],))
        couple = dict(cursor.fetchone())

        # Build Context
        input_payload = {
            "wedding_id": wedding["id"],
            "couple_name": couple["name"],
            "budget_total": wedding["budget_total"],
            "currency": wedding["currency"],
            "guest_count": wedding["guest_count_estimate"],
            "region": wedding["region"],
            "ceremony_type": wedding["ceremony_type"],
            "style_notes": wedding["style_notes"],
            "wedding_date": wedding["wedding_date"],
            "wedding_date_start": wedding["wedding_date_start"],
            "wedding_date_end": wedding["wedding_date_end"]
        }

        # Call LLM
        client = get_client(api_key)
        prompt = f"Create a wedding plan for the following profile:\n{json.dumps(input_payload, indent=2)}"
        
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=IntakeResult,
                temperature=0.2
            )
        )
        
        result_dict = json.loads(response.text)
        
        latency = int((time.time() - start_time) * 1000)
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        external_api_calls = [{
            "provider": "google",
            "model": model,
            "latency_ms": latency,
            "tokens": {"input": tokens_in, "output": tokens_out}
        }]
        
        # 2. Check Guardrails
        if not result_dict.get("is_budget_realistic", True):
            # Guardrail Blocked Path
            cursor.execute("""
                UPDATE agent_decision_logs 
                SET status = 'blocked_by_guardrail', error_kind = 'intake_validation', 
                    error_message = ?, rationale_summary = ?, 
                    input_payload = ?, output_payload = ?, confidence_score = ?,
                    latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
                WHERE id = ?
            """, (
                result_dict.get("guardrail_warning"),
                result_dict.get("rationale_summary"),
                json.dumps(input_payload),
                response.text,
                result_dict.get("confidence_score"),
                latency, tokens_in, tokens_out,
                json.dumps(external_api_calls),
                decision_id
            ))
            conn.commit()
            conn.close()
            return {"status": "blocked", "warning": result_dict.get("guardrail_warning"), "log_id": decision_id}
        
        # 2b. Validate every budget category against the whitelist. If the LLM
        # invents a non-canonical category, block the whole run so downstream
        # supplier_matcher lookups (WHERE category = ?) don't silently miss.
        # Normalize first so 'Venue' / 'VENUE' / ' venue ' all match.
        invalid_categories = sorted({
            _normalize_category(line.get("category")) or repr(line.get("category"))
            for line in result_dict.get("budget_lines", [])
            if _normalize_category(line.get("category")) not in ALLOWED_BUDGET_CATEGORIES
        })
        if invalid_categories:
            guardrail_message = (
                f"Invalid budget categories produced by intake_planner: {invalid_categories}. "
                f"Allowed categories: {sorted(ALLOWED_BUDGET_CATEGORIES)}."
            )
            cursor.execute("""
                UPDATE agent_decision_logs
                SET status = 'blocked_by_guardrail', error_kind = 'category_whitelist',
                    error_message = ?, rationale_summary = ?,
                    input_payload = ?, output_payload = ?, confidence_score = ?,
                    latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
                WHERE id = ?
            """, (
                guardrail_message,
                "Intake plan rejected: budget contains non-canonical category labels.",
                json.dumps(input_payload),
                response.text,
                result_dict.get("confidence_score"),
                latency, tokens_in, tokens_out,
                json.dumps(external_api_calls),
                decision_id
            ))
            conn.commit()
            conn.close()
            return {"status": "blocked", "warning": guardrail_message, "log_id": decision_id}

        # 3. Success Path — Mutate Domain Entities in a Single DB Transaction
        cursor.execute("UPDATE weddings SET status = 'planning' WHERE id = ?", (wedding_id,))

        # Seed Budget Lines. Normalize the category so downstream
        # `WHERE category = ?` queries (supplier_matcher, quote_extractor)
        # match regardless of LLM casing variance.
        budget_lines_to_insert = []
        for line in result_dict.get("budget_lines", []):
            line_id = f"bl_{uuid.uuid4().hex[:10]}"
            budget_lines_to_insert.append((
                line_id, wedding_id, _normalize_category(line["category"]),
                line["allocated_amount"], 0.0
            ))
        cursor.executemany("""
            INSERT INTO budget_lines (id, wedding_id, category, allocated_amount, spent_amount)
            VALUES (?, ?, ?, ?, ?)
        """, budget_lines_to_insert)
        
        # Seed Timeline Items
        timeline_items_to_insert = []
        wedding_date_str = wedding.get("wedding_date")
        if not wedding_date_str:
            wedding_date_str = wedding.get("wedding_date_start")
        
        if wedding_date_str:
            base_date = datetime.strptime(wedding_date_str, "%Y-%m-%d")
        else:
            base_date = datetime.now() + timedelta(days=365) # fallback to 1 year
            
        for item in result_dict.get("timeline_items", []):
            item_id = f"ti_{uuid.uuid4().hex[:10]}"
            due_date = base_date - timedelta(days=int(item["months_before"] * 30.5))
            due_at_str = due_date.strftime("%Y-%m-%d")
            
            timeline_items_to_insert.append((
                item_id, wedding_id, item["kind"], item["title"], item["description"], due_at_str, "todo", decision_id
            ))
        cursor.executemany("""
            INSERT INTO timeline_items (id, wedding_id, kind, title, description, due_at, status, generated_by_agent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, timeline_items_to_insert)
        
        # Update Log
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'success', rationale_summary = ?, 
                input_payload = ?, output_payload = ?, confidence_score = ?,
                latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
            WHERE id = ?
        """, (
            result_dict.get("rationale_summary"),
            json.dumps(input_payload),
            response.text,
            result_dict.get("confidence_score"),
            latency, tokens_in, tokens_out,
            json.dumps(external_api_calls),
            decision_id
        ))
        
        conn.commit()
        conn.close()
        return {"status": "success", "summary": result_dict.get("rationale_summary"), "log_id": decision_id}
        
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        conn.rollback()  # Roll back modifications if anything failed
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'error', error_kind = 'api_error', error_message = ?, latency_ms = ?
            WHERE id = ?
        """, (str(e), latency, decision_id))
        conn.commit()
        conn.close()
        raise e


def run_venue_matcher(wedding_id, user_id=None, api_key=None, model_name=None):
    """
    Matches available venues against the wedding profile and creates shortlisted bookings.
    """
    agent_id = "venue_matcher"
    model = model_name or model_for(agent_id)
    decision_id = str(uuid.uuid4())
    start_time = time.time()
    
    system_instruction = (
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
    prompt_version = get_prompt_version(system_instruction)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    _assert_wedding_exists(conn, cursor, wedding_id)
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, model_id, prompt_version, wedding_id, user_id, trigger, decision_type, status)
        VALUES (?, ?, ?, ?, ?, ?, 'couple_action', 'venue_match', 'pending')
    """, (decision_id, agent_id, model, prompt_version, wedding_id, user_id))
    conn.commit()

    try:
        # Gather wedding and venues context
        cursor.execute("SELECT * FROM weddings WHERE id = ?", (wedding_id,))
        wedding = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM budget_lines WHERE wedding_id = ? AND category = 'venue'", (wedding_id,))
        venue_budget_row = cursor.fetchone()
        venue_budget = dict(venue_budget_row)["allocated_amount"] if venue_budget_row else wedding["budget_total"] * 0.4

        venues_list = db.get_all_venues()

        # Pre-filter venues by capacity constraints
        guest_count = wedding["guest_count_estimate"]
        preferred_region = wedding["region"]

        venues_by_capacity = [
            v for v in venues_list
            if (v["capacity_min"] is None or v["capacity_min"] <= guest_count) and
               (v["capacity_max"] is None or v["capacity_max"] >= guest_count)
        ]

        # Prioritize the preferred region. region_matches honors the
        # province→county hierarchy so a "Leinster" selection picks up
        # venues seeded as "Meath", "Offaly", etc. and vice versa.
        venues_in_region = [v for v in venues_by_capacity if region_matches(v["region"], preferred_region)]

        if len(venues_in_region) >= 3:
            filtered_venues = venues_in_region
        else:
            # Include capacity-matching venues from other regions as backup candidates
            other_venues = [v for v in venues_by_capacity if not region_matches(v["region"], preferred_region)]
            filtered_venues = venues_in_region + other_venues[:(3 - len(venues_in_region))]

        # Build Context. venues_matching_region_count surfaces the pre-filter
        # signal: when it's 0, the candidate list is a fallback from adjacent
        # regions and the rationale_summary must say so.
        input_payload = {
            "wedding_profile": {
                "guest_count": guest_count,
                "region_preference": preferred_region,
                "venues_matching_region_count": len(venues_in_region),
                "allocated_venue_budget": venue_budget,
                "style_notes": wedding["style_notes"],
                "ceremony_type": wedding["ceremony_type"]
            },
            "available_venues": [
                {
                    "id": v["id"],
                    "name": v["name"],
                    "address": v["address"],
                    "region": v["region"],
                    "type": v["venue_type"],
                    "capacity": {"min": v["capacity_min"], "max": v["capacity_max"]},
                    "accommodation": v["on_site_accommodation"],
                    "pricing": json.loads(v["pricing_summary"]) if v["pricing_summary"] else {}
                } for v in filtered_venues
            ]
        }

        client = get_client(api_key)
        prompt = f"Match venues for the following couple profile and options:\n{json.dumps(input_payload, indent=2)}"
        
        response = client.models.generate_content(
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
        
        latency = int((time.time() - start_time) * 1000)
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        external_api_calls = [{
            "provider": "google",
            "model": model,
            "latency_ms": latency,
            "tokens": {"input": tokens_in, "output": tokens_out}
        }]
        
        # Pre-validate vendor_id ∈ filtered_venues (to prevent DB crash on hallucinations)
        valid_venue_ids = {v["id"] for v in filtered_venues}
        bookings_to_insert = []
        hallucinated_ids = []
        
        for match in result_dict.get("shortlist", []):
            v_id = match["vendor_id"]
            if v_id in valid_venue_ids:
                # Idempotency check: don't insert duplicate booking
                cursor.execute("SELECT id FROM bookings WHERE wedding_id = ? AND venue_id = ?", (wedding_id, v_id))
                if not cursor.fetchone():
                    booking_id = f"bkv_{uuid.uuid4().hex[:10]}"
                    bookings_to_insert.append((
                        booking_id, wedding_id, v_id, "shortlisted", decision_id
                    ))
            else:
                hallucinated_ids.append(v_id)
                
        if hallucinated_ids:
            # Guardrail Blocked Path
            cursor.execute("""
                UPDATE agent_decision_logs 
                SET status = 'blocked_by_guardrail', error_kind = 'hallucination_guardrail', 
                    error_message = ?, rationale_summary = ?, 
                    input_payload = ?, output_payload = ?, confidence_score = ?,
                    latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
                WHERE id = ?
            """, (
                f"Agent suggested hallucinated venue IDs: {hallucinated_ids}",
                "Venue matcher execution blocked due to venue ID hallucination.",
                json.dumps(input_payload),
                response.text,
                result_dict.get("confidence_score"),
                latency, tokens_in, tokens_out,
                json.dumps(external_api_calls),
                decision_id
            ))
            conn.commit()
            conn.close()
            return {"status": "blocked", "warning": f"Hallucinated venue IDs detected: {hallucinated_ids}", "log_id": decision_id}
            
        # Mutate Domain Entities: Insert shortlisted Bookings
        cursor.executemany("""
            INSERT INTO bookings (id, wedding_id, venue_id, status, sourced_by_agent_id)
            VALUES (?, ?, ?, ?, ?)
        """, bookings_to_insert)
        
        # Write success log
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'success', rationale_summary = ?, 
                input_payload = ?, output_payload = ?, confidence_score = ?,
                latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
            WHERE id = ?
        """, (
            result_dict.get("rationale_summary"),
            json.dumps(input_payload),
            response.text,
            result_dict.get("confidence_score"),
            latency, tokens_in, tokens_out,
            json.dumps(external_api_calls),
            decision_id
        ))
        
        conn.commit()
        conn.close()
        return {"status": "success", "shortlist": result_dict.get("shortlist"), "summary": result_dict.get("rationale_summary"), "log_id": decision_id}
        
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        conn.rollback()  # Ensure database is rolled back on error
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'error', error_kind = 'api_error', error_message = ?, latency_ms = ?
            WHERE id = ?
        """, (str(e), latency, decision_id))
        conn.commit()
        conn.close()
        raise e


def run_supplier_matcher(wedding_id, category, user_id=None, api_key=None, model_name=None):
    """
    Matches available suppliers for a specific category against the wedding profile and creates shortlisted bookings.
    """
    agent_id = "supplier_matcher"
    model = model_name or model_for(agent_id)
    decision_id = str(uuid.uuid4())
    start_time = time.time()
    
    system_instruction = (
        f"You are an expert Irish wedding coordinator agent called supplier_matcher. Your job is to match the couple's "
        f"wedding profile with available suppliers in the category: '{category}'.\n\n"
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
    prompt_version = get_prompt_version(system_instruction)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    _assert_wedding_exists(conn, cursor, wedding_id)
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, model_id, prompt_version, wedding_id, user_id, trigger, decision_type, status)
        VALUES (?, ?, ?, ?, ?, ?, 'couple_action', 'supplier_match', 'pending')
    """, (decision_id, agent_id, model, prompt_version, wedding_id, user_id))
    conn.commit()

    try:
        # Gather wedding and suppliers context
        cursor.execute("SELECT * FROM weddings WHERE id = ?", (wedding_id,))
        wedding = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM budget_lines WHERE wedding_id = ? AND category = ?", (wedding_id, category))
        budget_row = cursor.fetchone()
        allocated_budget = dict(budget_row)["allocated_amount"] if budget_row else wedding["budget_total"] * 0.1

        cursor.execute("SELECT * FROM suppliers WHERE category = ?", (category,))
        suppliers_list = [dict(r) for r in cursor.fetchall()]

        # Pre-filter suppliers by region preference. Suppliers store their
        # geography in `location`, which currently uses the same county/province
        # vocabulary as venues, so region_matches works identically.
        preferred_region = wedding["region"]
        suppliers_in_region = [s for s in suppliers_list if region_matches(s["location"], preferred_region)]

        if len(suppliers_in_region) >= 3:
            filtered_suppliers = suppliers_in_region
        else:
            # Include other regions as backup options
            other_suppliers = [s for s in suppliers_list if not region_matches(s["location"], preferred_region)]
            filtered_suppliers = suppliers_in_region + other_suppliers[:(3 - len(suppliers_in_region))]

        # Build Context
        input_payload = {
            "category": category,
            "wedding_profile": {
                "guest_count": wedding["guest_count_estimate"],
                "region_preference": preferred_region,
                "allocated_budget": allocated_budget,
                "style_notes": wedding["style_notes"]
            },
            "available_suppliers": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "location": s["location"],
                    "pricing": json.loads(s["pricing_summary"]) if s["pricing_summary"] else {},
                    "attributes": json.loads(s["attributes"]) if s["attributes"] else {}
                } for s in filtered_suppliers
            ]
        }

        client = get_client(api_key)
        prompt = f"Match suppliers for the following couple profile and options:\n{json.dumps(input_payload, indent=2)}"
        
        response = client.models.generate_content(
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
        
        latency = int((time.time() - start_time) * 1000)
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        external_api_calls = [{
            "provider": "google",
            "model": model,
            "latency_ms": latency,
            "tokens": {"input": tokens_in, "output": tokens_out}
        }]
        
        # Pre-validate vendor_id ∈ filtered_suppliers (to prevent DB crash on hallucinations)
        valid_supplier_ids = {s["id"] for s in filtered_suppliers}
        bookings_to_insert = []
        hallucinated_ids = []
        
        for match in result_dict.get("shortlist", []):
            s_id = match["vendor_id"]
            if s_id in valid_supplier_ids:
                # Idempotency check: don't insert duplicate booking
                cursor.execute("SELECT id FROM bookings WHERE wedding_id = ? AND supplier_id = ?", (wedding_id, s_id))
                if not cursor.fetchone():
                    booking_id = f"bks_{uuid.uuid4().hex[:10]}"
                    bookings_to_insert.append((
                        booking_id, wedding_id, s_id, "shortlisted", decision_id
                    ))
            else:
                hallucinated_ids.append(s_id)
                
        if hallucinated_ids:
            # Guardrail Blocked Path
            cursor.execute("""
                UPDATE agent_decision_logs 
                SET status = 'blocked_by_guardrail', error_kind = 'hallucination_guardrail', 
                    error_message = ?, rationale_summary = ?, 
                    input_payload = ?, output_payload = ?, confidence_score = ?,
                    latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
                WHERE id = ?
            """, (
                f"Agent suggested hallucinated supplier IDs: {hallucinated_ids}",
                "Supplier matcher execution blocked due to supplier ID hallucination.",
                json.dumps(input_payload),
                response.text,
                result_dict.get("confidence_score"),
                latency, tokens_in, tokens_out,
                json.dumps(external_api_calls),
                decision_id
            ))
            conn.commit()
            conn.close()
            return {"status": "blocked", "warning": f"Hallucinated supplier IDs detected: {hallucinated_ids}", "log_id": decision_id}
            
        # Mutate Domain Entities: Insert shortlisted Bookings
        cursor.executemany("""
            INSERT INTO bookings (id, wedding_id, supplier_id, status, sourced_by_agent_id)
            VALUES (?, ?, ?, ?, ?)
        """, bookings_to_insert)
        
        # Write success log
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'success', rationale_summary = ?, 
                input_payload = ?, output_payload = ?, confidence_score = ?,
                latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
            WHERE id = ?
        """, (
            result_dict.get("rationale_summary"),
            json.dumps(input_payload),
            response.text,
            result_dict.get("confidence_score"),
            latency, tokens_in, tokens_out,
            json.dumps(external_api_calls),
            decision_id
        ))
        
        conn.commit()
        conn.close()
        return {"status": "success", "shortlist": result_dict.get("shortlist"), "summary": result_dict.get("rationale_summary"), "log_id": decision_id}
        
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        conn.rollback()  # Roll back transaction on exception
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'error', error_kind = 'api_error', error_message = ?, latency_ms = ?
            WHERE id = ?
        """, (str(e), latency, decision_id))
        conn.commit()
        conn.close()
        raise e


def run_quote_extractor(booking_id, email_text, user_id=None, api_key=None, model_name=None):
    """
    Parses a vendor email reply, extracts structured quote line items, total, and availability.
    Also transitions booking status and flags budget alerts if quote exceeds budget.
    """
    agent_id = "quote_extractor"
    model = model_name or model_for(agent_id)
    decision_id = str(uuid.uuid4())
    start_time = time.time()
    
    system_instruction = (
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
    prompt_version = get_prompt_version(system_instruction)
    
    conn = db.get_connection()
    cursor = conn.cursor()

    # Find Booking details to get wedding and supplier information.
    # Run before the pending log INSERT so a missing booking does not leave a stuck row.
    cursor.execute("""
        SELECT b.*, w.id as wedding_id, w.budget_total,
               s.name as supplier_name, s.category as supplier_category,
               v.name as venue_name
        FROM bookings b
        JOIN weddings w ON b.wedding_id = w.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        LEFT JOIN venues v ON b.venue_id = v.id
        WHERE b.id = ?
    """, (booking_id,))
    booking = dict(cursor.fetchone())

    wedding_id = booking["wedding_id"]
    # B2: derive category explicitly. The DB CHECK constraint enforces
    # (venue_id XOR supplier_id) today, but if a future booking type
    # bypasses that we want a loud failure rather than a silent route
    # into the wrong budget line.
    if booking["supplier_id"]:
        category = booking["supplier_category"]
        vendor_name = booking["supplier_name"]
    elif booking["venue_id"]:
        category = "venue"
        vendor_name = booking["venue_name"]
    else:
        conn.close()
        raise ValueError(
            f"Booking {booking_id!r} has neither supplier_id nor venue_id; "
            f"cannot derive category for quote extraction."
        )

    # 1. Initialize Log. parent_decision_id links this extraction to the
    # action that produced the email we're parsing — typically the
    # inquiry_send for this booking, falling back to the matcher decision
    # that sourced the booking. Closes the chain
    # matcher → inquiry_send → quote_extract for judge-facing traceability.
    parent_decision_id = _resolve_quote_extract_parent(cursor, booking_id)
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, model_id, prompt_version, wedding_id, user_id, booking_id, parent_decision_id, trigger, decision_type, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'supplier_response', 'quote_draft', 'pending')
    """, (decision_id, agent_id, model, prompt_version, wedding_id, user_id, booking_id, parent_decision_id))
    conn.commit()

    try:
        # Get budget line allocated for this category
        cursor.execute("SELECT * FROM budget_lines WHERE wedding_id = ? AND category = ?", (wedding_id, category))
        budget_row = cursor.fetchone()
        allocated_amount = dict(budget_row)["allocated_amount"] if budget_row else 0.0

        input_payload = {
            "booking_id": booking_id,
            "vendor_name": vendor_name,
            "category": category,
            "allocated_budget": allocated_amount,
            "email_text": email_text
        }

        client = get_client(api_key)
        
        response = client.models.generate_content(
            model=model,
            contents=email_text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=QuoteResult,
                temperature=0.1
            )
        )
        
        result_dict = json.loads(response.text)
        
        latency = int((time.time() - start_time) * 1000)
        tokens_in = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        tokens_out = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        external_api_calls = [{
            "provider": "google",
            "model": model,
            "latency_ms": latency,
            "tokens": {"input": tokens_in, "output": tokens_out}
        }]
        
        total_amount = result_dict.get("total_amount", 0.0)
        is_available = result_dict.get("is_available", True)
        
        # Write quote details to database
        quote_id = f"q_{uuid.uuid4().hex[:10]}"
        line_items_json = json.dumps(result_dict.get("line_items", []))
        
        cursor.execute("""
            INSERT INTO quotes (id, booking_id, line_items, total_amount, currency, status, generated_by_agent_id, rationale_text)
            VALUES (?, ?, ?, ?, ?, 'pending', 'quote_extractor', ?)
        """, (quote_id, booking_id, line_items_json, total_amount, result_dict.get("currency", "EUR"), result_dict.get("rationale_text")))
        
        # Transition Booking Status
        new_booking_status = "quoted" if is_available else "declined"
        cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_booking_status, booking_id))
        
        # 2. Check for Budget Alert (If quote total > allocated budget line)
        budget_alert_log_id = None
        if total_amount > allocated_amount and allocated_amount > 0:
            budget_alert_log_id = str(uuid.uuid4())
            alert_text = f"Budget alert for category '{category}': quote from {vendor_name} (€{total_amount:,.2f}) exceeds allocated budget (€{allocated_amount:,.2f}) by €{total_amount - allocated_amount:,.2f}."
            cursor.execute("""
                INSERT INTO agent_decision_logs (id, agent_id, model_id, prompt_version, wedding_id, user_id, booking_id, parent_decision_id, trigger, decision_type, status, rationale_summary, input_payload, output_payload, external_api_calls)
                VALUES (?, 'budget_monitor', ?, ?, ?, ?, ?, ?, 'parent_decision', 'budget_alert', 'success', ?, ?, ?, ?)
            """, (
                budget_alert_log_id, model, prompt_version, wedding_id, user_id, booking_id, decision_id,
                alert_text, 
                json.dumps({"allocated": allocated_amount, "quote_total": total_amount}),
                json.dumps({"alert_message": alert_text, "category": category}),
                '[]'
            ))
            
        # Update main quote log
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'success', rationale_summary = ?, 
                input_payload = ?, output_payload = ?, confidence_score = ?,
                latency_ms = ?, tokens_input = ?, tokens_output = ?, external_api_calls = ?
            WHERE id = ?
        """, (
            f"Extracted quote of €{total_amount:,.2f} from {vendor_name} ({'Available' if is_available else 'Unavailable'}).",
            json.dumps(input_payload),
            response.text,
            result_dict.get("confidence_score"),
            latency, tokens_in, tokens_out,
            json.dumps(external_api_calls),
            decision_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "quote_id": quote_id, 
            "total_amount": total_amount, 
            "is_available": is_available,
            "budget_warning": total_amount > allocated_amount,
            "log_id": decision_id,
            "alert_log_id": budget_alert_log_id
        }
        
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        conn.rollback()  # Roll back database transactions on error
        cursor.execute("""
            UPDATE agent_decision_logs 
            SET status = 'error', error_kind = 'api_error', error_message = ?, latency_ms = ?
            WHERE id = ?
        """, (str(e), latency, decision_id))
        conn.commit()
        conn.close()
        raise e
