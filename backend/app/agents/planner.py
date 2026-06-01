import json
import logging
import uuid
from datetime import datetime, timedelta, date
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import Wedding, User, BudgetLine, TimelineItem
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version
from app.utils.constants import ALLOWED_BUDGET_CATEGORIES, normalize_category

logger = logging.getLogger(__name__)

# Pydantic Schemas for Gemini Structured Outputs
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
    is_budget_realistic: bool = Field(description="False if the budget is clearly too low for the estimated guest count in that Irish region (e.g. €5,000 for 150 guests in Dublin). True otherwise.")
    guardrail_warning: str = Field(description="Reason why the budget is unrealistic (with Irish market-rate comparisons), or empty if realistic.")
    budget_lines: list[BudgetLineDraft] = Field(description="Allocated budget split across categories.")
    timeline_items: list[TimelineItemDraft] = Field(description="Timeline planning milestones.")
    rationale_summary: str = Field(description="A short summary of the generated plan or guardrail violation.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 representing the agent's confidence.")


SYSTEM_INSTRUCTION = (
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

@run_agent("intake_planner", "timeline_generate")
async def run_intake_planner(db: AsyncSession, wedding_id: str, force: bool = False):
    """Orchestrates intake analysis and seeds timeline & budget allocations.

    When ``force`` is True the budget-realism guardrail is acknowledged rather
    than blocking: the warning is still recorded on the decision log (so the
    audit trail and the "AI flagged this" signal are preserved), but the agent
    proceeds to build the plan anyway. This powers the couple's
    "continue anyway" choice after the guardrail fires.
    """
    agent_id = "intake_planner"
    model = model_for(agent_id)
    prompt_version = get_prompt_version(SYSTEM_INSTRUCTION)
    
    # 1. Fetch wedding and couple info
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise ValueError(f"Wedding not found: {wedding_id}")
        
    couple_result = await db.exec(select(User).where(User.id == wedding.couple_user_id))
    couple = couple_result.first()
    if not couple:
        raise ValueError(f"Couple user not found for ID: {wedding.couple_user_id}")
        
    # 2. Formulate context payload
    input_payload = {
        "wedding_id": str(wedding.id),
        "couple_name": couple.name,
        "budget_total": wedding.budget_total,
        "currency": wedding.currency,
        "guest_count": wedding.guest_count_estimate,
        "region": wedding.region,
        "ceremony_type": wedding.ceremony_type,
        "style_notes": wedding.style_notes,
        "wedding_date": str(wedding.wedding_date) if wedding.wedding_date else None,
        "wedding_date_start": str(wedding.wedding_date_start) if wedding.wedding_date_start else None,
        "wedding_date_end": str(wedding.wedding_date_end) if wedding.wedding_date_end else None
    }
    
    client = get_client()
    prompt = f"Create a wedding plan for the following profile:\n{json.dumps(input_payload, indent=2)}"
    
    # Call Gemini asynchronously
    logger.info(f"Invoking {model} for intake planner...")
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=IntakeResult,
            temperature=0.2
        )
    )
    
    result_dict = json.loads(response.text)
    
    # Track API call for XPRIZE logging
    usage = response.usage_metadata
    api_calls = [{
        "provider": "google",
        "model": model,
        "tokens": {
            "input": usage.prompt_token_count if usage else 0,
            "output": usage.candidates_token_count if usage else 0
        }
    }]
    
    # 3. Check budget realism guardrail
    if not result_dict.get("is_budget_realistic", True) and not force:
        return (
            {
                "status": "blocked",
                "error_kind": "intake_validation",
                "warning": result_dict.get("guardrail_warning"),
                "rationale_summary": "Intake plan rejected: budget is unrealistic for guest count in this region."
            },
            result_dict.get("confidence_score", 0.0),
            model,
            prompt_version,
            api_calls
        )

    # 4. Check category whitelist guardrail
    invalid_categories = sorted({
        normalize_category(line.get("category")) or repr(line.get("category"))
        for line in result_dict.get("budget_lines", [])
        if normalize_category(line.get("category")) not in ALLOWED_BUDGET_CATEGORIES
    })
    
    if invalid_categories:
        warning_msg = f"Invalid budget categories: {invalid_categories}. Allowed: {ALLOWED_BUDGET_CATEGORIES}"
        return (
            {
                "status": "blocked",
                "error_kind": "category_whitelist",
                "warning": warning_msg,
                "rationale_summary": "Intake plan rejected: budget contains non-canonical category labels."
            },
            result_dict.get("confidence_score", 0.0),
            model,
            prompt_version,
            api_calls
        )

    # 5. Success Path: Mutate Database
    # The planner runs for FREE at intake to produce the teaser (budget + timeline),
    # so success lands the wedding in 'preview' — not 'planning'. Payment is what
    # promotes it to 'planning' and unlocks the (paid) venue/supplier cascade.
    wedding.status = "preview"
    db.add(wedding)
    
    # Seed budget lines
    for line in result_dict.get("budget_lines", []):
        cat = normalize_category(line["category"])
        budget_line = BudgetLine(
            id=f"bl_{uuid.uuid4().hex[:10]}",
            wedding_id=wedding.id,
            category=cat,
            allocated_amount=line["allocated_amount"],
            spent_amount=0.0
        )
        db.add(budget_line)
        
    # Seed timeline items
    wedding_date_str = wedding.wedding_date or wedding.wedding_date_start
    if wedding_date_str:
        # Check if date is date object or string
        base_date = wedding_date_str if isinstance(wedding_date_str, date) else datetime.strptime(wedding_date_str, "%Y-%m-%d").date()
    else:
        base_date = date.today() + timedelta(days=365)  # 1 year out fallback
        
    for item in result_dict.get("timeline_items", []):
        days_before = int(item["months_before"] * 30.5)
        due_at = base_date - timedelta(days=days_before)
        
        timeline_item = TimelineItem(
            id=f"ti_{uuid.uuid4().hex[:10]}",
            wedding_id=wedding.id,
            kind=item["kind"],
            title=item["title"],
            description=item["description"],
            due_at=due_at,
            status="todo",
            generated_by_agent_id=agent_id
        )
        db.add(timeline_item)
        
    # Return details for log recording
    return (
        result_dict,
        result_dict.get("confidence_score", 1.0),
        model,
        prompt_version,
        api_calls
    )
