import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import Wedding
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version
from app.agents.privacy import send_prompt
from app.utils.constants import ALLOWED_BUDGET_CATEGORIES, normalize_category

logger = logging.getLogger(__name__)

# Pydantic Schemas for Gemini Structured Outputs
class BudgetLineDraft(BaseModel):
    category: str = Field(description=f"Must be one of: {', '.join(sorted(ALLOWED_BUDGET_CATEGORIES))}")
    allocated_amount: float = Field(description="Amount allocated in EUR")
    rationale: str = Field(description="Brief explanation of why this amount was allocated")

class IntakeResult(BaseModel):
    is_budget_realistic: bool = Field(description="False if the budget is clearly too low for the estimated guest count in that Irish region (e.g. €5,000 for 150 guests in Dublin). True otherwise.")
    guardrail_warning: str = Field(description="Reason why the budget is unrealistic (with Irish market-rate comparisons), or empty if realistic.")
    budget_lines: list[BudgetLineDraft] = Field(description="Allocated budget split across categories.")
    rationale_summary: str = Field(description="A short summary of the generated plan or guardrail violation.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 representing the agent's confidence.")


SYSTEM_INSTRUCTION = (
    "You are an expert Irish wedding coordinator. Your job is to draft a comprehensive budget allocation "
    "for a couple based on their intake form. You must validate if their budget is realistic.\n\n"
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
    "- 'Irish Catholic': Seed budget lines including a church donation/fee (~€400-500) and standard allocations.\n"
    "- 'Civil/Humanist': Seed budget lines with an officiant fee (~€350-450) and omit church donation.\n"
    "- 'Hindu': Seed splits with decoration/mandap and multi-day elements (Mehndi, Sangeet) taking a higher split (~12% on decor/florals, 10% on pre-wedding events).\n"
    "- 'Multi-cultural': Merge Catholic/Hindu or Civil/Hindu elements and explain in rationales.\n"
    "Return valid JSON conforming to the response schema."
)

# The market rules above are Irish and in euros, so they can't judge any other budget
# (B11). Without a total there is nothing to check (PD-009).
SKIP_SUMMARIES = {
    "no_budget": "Budget check not run: the couple haven't set a total budget yet.",
    "not_irish_pricing": "Budget check not run: the planner's price guide covers Irish "
                         "weddings in euros only, so it can't judge this budget.",
}


def _skip_reason(wedding: Wedding) -> Optional[str]:
    if wedding.budget_total is None:
        return "no_budget"
    if (wedding.currency or "").upper() != "EUR":
        return "not_irish_pricing"
    return None


@run_agent("intake_planner", "intake_plan")
async def run_intake_planner(db: AsyncSession, wedding_id: str, force: bool = False):
    """Checks the intake profile and drafts a budget split, kept in the decision log.

    With no total budget, or a wedding outside the Irish euro price guide, it skips
    the model call and moves the wedding to planning, so setup never stalls (PD-009).

    The planning checklist (PD-007) replaced the generated timeline, so this agent no
    longer writes timeline items, even if the model returns some.

    When ``force`` is True the budget-realism guardrail is acknowledged rather
    than blocking: the warning is still recorded on the decision log (so the
    audit trail and the "AI flagged this" signal are preserved), but the agent
    proceeds to build the plan anyway. This powers the couple's
    "continue anyway" choice after the guardrail fires.
    """
    agent_id = "intake_planner"
    model = model_for(agent_id)
    prompt_version = get_prompt_version(SYSTEM_INSTRUCTION)
    
    # 1. Fetch the wedding
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise ValueError(f"Wedding not found: {wedding_id}")

    skip_reason = _skip_reason(wedding)
    if skip_reason:
        # No model call, so there is no model, prompt, confidence or token count to record.
        wedding.status = "planning"
        db.add(wedding)
        return (
            {"budget_check": "skipped", "skip_reason": skip_reason,
             "rationale_summary": SKIP_SUMMARIES[skip_reason]},
            None, None, None, [],
        )

    # 2. Formulate context payload. The couple's names stay out (PD-009, rule 3).
    input_payload = {
        "wedding_id": str(wedding.id),
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
    prompt = f"Create a wedding plan for the following profile:\n{json.dumps(input_payload, indent=2, ensure_ascii=False)}"
    
    # Call Gemini asynchronously
    logger.info(f"Invoking {model} for intake planner...")
    response = await send_prompt(
        db, wedding_id, client,
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
            result_dict.get("confidence_score"),
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
            result_dict.get("confidence_score"),
            model,
            prompt_version,
            api_calls
        )

    # 5. Success Path: Mutate Database
    # Success moves the wedding into planning (PD-003 removed the paid "preview" stage).
    wedding.status = "planning"
    db.add(wedding)
    
    # The draft budget lines stay in the decision log only. The couple's budget is the
    # PD-004 dollar tables, which they fill in themselves (or from the AI split they ask
    # for); the old euro BudgetLine rows are no longer created (B42).

    # Return details for log recording
    return (
        result_dict,
        result_dict.get("confidence_score"),
        model,
        prompt_version,
        api_calls
    )
