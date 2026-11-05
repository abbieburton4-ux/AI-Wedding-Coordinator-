"""Suggests a starting split of the couple's own total across budget categories (PD-004).

The model returns only percentage shares; the dollar amounts are worked out here, in
whole cents, from the total the couple set. So the agent can't invent a vendor price,
and the amounts always add up to exactly the total. It saves nothing: the couple see
the split as a suggestion and decide whether to use it.
"""
import json
import logging
import re
from typing import Optional

from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import get_client, get_prompt_version, model_for
from app.agents.orchestrator import run_agent
from app.utils.constants import ALLOWED_BUDGET_CATEGORIES, normalize_category

logger = logging.getLogger(__name__)

AGENT_ID = "budget_splitter"

# Shares are accepted if they add up to 100% give or take this much, then scaled to
# the exact total. Further off than this means the model didn't produce a real split.
SHARE_TOLERANCE_BP = 100  # basis points (1%)

# Money amounts in the model's prose: a currency sign or code next to digits, or "15k".
# Percentages and plain counts ("40%", "150 guests") are fine (rule 2: no invented prices).
PRICE_TEXT = re.compile(
    r"[$€£¥]\s*\d"
    r"|\d\s*[$€£¥]"
    r"|\b(?:usd|eur|gbp|cad|aud)\s*\d"
    r"|\d[\d,.]*\s*(?:usd|eur|gbp|cad|aud|dollars?|euros?|pounds?|bucks|grand)\b"
    r"|\b\d+(?:[.,]\d+)?\s?k\b",
    re.IGNORECASE,
)


class SplitLineDraft(BaseModel):
    category: str = Field(
        description="One of the couple's own category names, spelt exactly as given, "
        "or one of the standard categories listed in the prompt."
    )
    percent: float = Field(description="Share of the couple's total, from 0 to 100.")
    rationale: str = Field(description="One short sentence on why this share. No prices.")


class SplitResult(BaseModel):
    lines: list[SplitLineDraft] = Field(description="The split. Shares add up to 100.")
    rationale_summary: str = Field(description="One or two sentences summarising the split.")


SYSTEM_INSTRUCTION = (
    "You help a couple make a first draft of their wedding budget. They give you their "
    "total, their own category names and a few facts about the wedding. Suggest what "
    "share of the total, as a percentage, each category could take.\n\n"
    "RULES:\n"
    "- Use the couple's own category names where they fit, spelt exactly as given. You "
    "may add standard categories from the list provided if something important is missing.\n"
    "- Return percentages only. Never state a price, a quote or a vendor's rate, and "
    "never name a vendor. The app works out the amounts from the couple's total.\n"
    "- The percentages must add up to 100.\n"
    "- Keep each rationale to one short, plain sentence.\n"
    "Return valid JSON conforming to the response schema."
)


def category_key(name) -> str:
    """One comparable form for a category name: 'Hair_Makeup', 'hair makeup' and
    ' HAIR  makeup ' are all 'hair makeup'."""
    return " ".join(normalize_category(name).replace("_", " ").split())


def _label(key: str) -> str:
    return key.capitalize()


def _no_prices(text, where: str, warnings: list) -> str:
    """Drops prose that states an amount of money; the app shows only its own sums."""
    if not isinstance(text, str):
        return ""
    if PRICE_TEXT.search(text):
        warnings.append(f"price-like text removed from {where}")
        return ""
    return text


def _blocked(error_kind: str, warning: str) -> dict:
    return {
        "status": "blocked",
        "error_kind": error_kind,
        "warning": warning,
        "rationale_summary": f"Split suggestion rejected: {warning}",
    }


def split_cents(total_cents: int, weights: list) -> list:
    """Share an integer total out by integer weights, exactly (largest remainder)."""
    weight_sum = sum(weights)
    base = [total_cents * w // weight_sum for w in weights]
    leftover = total_cents - sum(base)
    by_remainder = sorted(
        range(len(weights)), key=lambda i: (-(total_cents * weights[i] % weight_sum), i)
    )
    for i in by_remainder[:leftover]:
        base[i] += 1
    return base


def _token_count(usage, name: str) -> Optional[int]:
    value = getattr(usage, name, None) if usage is not None else None
    return value if isinstance(value, int) else None


@run_agent(AGENT_ID, "budget_split")
async def run_budget_splitter(
    db: AsyncSession,
    wedding_id: str,
    total_cents: int,
    category_names: list,
    guest_count: Optional[int] = None,
    ceremony_type: Optional[str] = None,
):
    model = model_for(AGENT_ID)
    prompt_version = get_prompt_version(SYSTEM_INSTRUCTION)

    if not isinstance(total_cents, int) or total_cents <= 0:
        return (_blocked("no_total", "the couple haven't set a total budget"),
                None, model, prompt_version)

    own = {}
    for name in category_names:
        own.setdefault(category_key(name), name)
    allowed = set(own) | {category_key(c) for c in ALLOWED_BUDGET_CATEGORIES}

    facts = {
        "total_budget_usd": f"{total_cents // 100}.{total_cents % 100:02d}",
        "couple_categories": list(own.values()),
        "standard_categories": sorted(ALLOWED_BUDGET_CATEGORIES),
        "guest_count": guest_count,
        "ceremony_type": ceremony_type,
    }
    client = get_client()
    response = await client.aio.models.generate_content(
        model=model,
        contents=f"Suggest a starting split for this budget:\n{json.dumps(facts, indent=2)}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SplitResult,
            temperature=0.2,
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    tokens = (_token_count(usage, "prompt_token_count"),
              _token_count(usage, "candidates_token_count"))
    api_calls = [{"provider": "google", "model": model,
                  "tokens": {"input": tokens[0], "output": tokens[1]}}]

    def done(result: dict):
        # No confidence is asked of the model, so none is recorded (rule 10).
        return result, None, model, prompt_version, api_calls, [], tokens

    data = json.loads(response.text)
    lines = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(lines, list) or not lines:
        return done(_blocked("empty_split", "the model returned no categories"))

    seen = set()
    weights = []
    picked = []
    warnings: list = []
    for line in lines:
        if not isinstance(line, dict):
            return done(_blocked("invalid_share", "a line wasn't readable"))
        key = category_key(line.get("category"))
        if key not in allowed:
            return done(_blocked(
                "category_whitelist", f"unknown category {line.get('category')!r}"
            ))
        label = own.get(key, _label(key))
        # Compared on the key and on the label shown, so two lines can never become two
        # categories with the same name.
        if key in seen or category_key(label) in seen:
            return done(_blocked("duplicate_category", f"{key!r} appears twice"))
        seen.update({key, category_key(label)})
        percent = line.get("percent")
        if isinstance(percent, bool) or not isinstance(percent, (int, float)) \
                or not 0 < percent <= 100:
            return done(_blocked("invalid_share", f"share for {key!r} isn't 0 to 100"))
        weights.append(int(round(percent * 100)))  # basis points
        picked.append({
            "name": label,
            "existing": key in own,
            "rationale": _no_prices(line.get("rationale"), f"the {label} reason", warnings),
        })

    if abs(sum(weights) - 10000) > SHARE_TOLERANCE_BP or 0 in weights:
        return done(_blocked("shares_dont_add_up", "the shares don't add up to 100%"))

    for item, cents in zip(picked, split_cents(total_cents, weights)):
        item["planned_cents"] = cents
    if sum(item["planned_cents"] for item in picked) != total_cents:
        return done(_blocked("split_mismatch", "the amounts don't add up to the total"))

    result = {
        "suggestion": True,
        "total_cents": total_cents,
        "lines": picked,
        "rationale_summary": _no_prices(data.get("rationale_summary"), "the summary", warnings),
    }
    if warnings:
        result["warnings"] = warnings
    return done(result)
