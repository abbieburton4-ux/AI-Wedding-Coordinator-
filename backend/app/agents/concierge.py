import json
import asyncio
import logging
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.genai import types
from app.db.models import Wedding, User, BudgetLine, ChecklistTask, Booking, Quote, Supplier, Venue
from app.utils.checklist import STAGE_BY_KEY, STAGE_KEYS, stage_due
from app.agents.orchestrator import run_agent
from app.agents.base import get_client, model_for, get_prompt_version

logger = logging.getLogger(__name__)


class ConciergeReply(BaseModel):
    reply: str = Field(description="A warm, concise answer grounded in the couple's real wedding data.")
    confidence_score: float = Field(description="Confidence in the answer, 0.0–1.0.")


SYSTEM_INSTRUCTION = (
    "You are Aurelia, an expert Irish wedding coordinator and the couple's personal AI concierge. "
    "Answer their question using the WEDDING CONTEXT provided (their budget allocations + spend, their "
    "planning checklist, and their shortlisted vendors) plus general Irish wedding knowledge.\n\n"
    "RULES:\n"
    "- Be warm and concise (2–5 sentences). Speak to the couple directly.\n"
    "- Be SPECIFIC with their real numbers: cite the relevant budget line's allocated vs spent, vendor "
    "names, quotes, and dates from the context.\n"
    "- For affordability questions, compare the category's allocated/spent against typical Irish market "
    "rates and tell them clearly whether it fits.\n"
    "- NEVER invent vendors, prices, or commitments that aren't in the context. If the info isn't there, "
    "say so plainly and suggest the next step (e.g. 'run the matcher', 'log the quote').\n"
    "- Use € and Irish context. Don't recite the whole context back — just answer the question.\n"
    "Return valid JSON conforming to the response schema."
)


async def _build_context(db: AsyncSession, wedding: Wedding) -> str:
    """Assembles a compact, factual snapshot of the couple's wedding for grounding."""
    couple = (await db.exec(select(User).where(User.id == wedding.couple_user_id))).first()
    budget = (await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding.id).order_by(BudgetLine.allocated_amount.desc())
    )).all()
    # Titles only: the couple's notes on a task stay out of the prompt.
    open_tasks = (await db.exec(
        select(ChecklistTask).where(ChecklistTask.wedding_id == wedding.id,
                                    ChecklistTask.done == False)  # noqa: E712
    )).all()
    open_tasks = sorted(open_tasks, key=lambda t: (
        STAGE_KEYS.index(t.stage) if t.stage in STAGE_BY_KEY else 0, t.position))
    bookings = (await db.exec(select(Booking).where(Booking.wedding_id == wedding.id))).all()

    lines: list[str] = []
    lines.append(f"Couple: {couple.name if couple else 'the couple'}")
    lines.append(
        f"Wedding: {wedding.guest_count_estimate} guests · {wedding.ceremony_type} · {wedding.region} · "
        f"date {wedding.wedding_date or 'TBD'}."
    )
    lines.append(f"Total budget: €{wedding.budget_total:,.0f}. Plan status: {wedding.status}.")

    if budget:
        lines.append("Budget lines (allocated / spent):")
        for b in budget:
            lines.append(f"  - {b.category}: €{b.allocated_amount:,.0f} allocated, €{b.spent_amount:,.0f} spent")

    if open_tasks:
        lines.append("Next unfinished checklist tasks:")
        for t in open_tasks[:8]:
            stage = STAGE_BY_KEY.get(t.stage)
            when = stage.label if stage else "no stage"
            if stage and wedding.wedding_date:
                when += f", due {stage_due(wedding.wedding_date, stage)} (provisional)"
            lines.append(f"  - {t.title} ({when})")

    if bookings:
        venues = {v.id: v for v in (await db.exec(select(Venue))).all()}
        suppliers = {s.id: s for s in (await db.exec(select(Supplier))).all()}
        quotes = (await db.exec(
            select(Quote).where(Quote.booking_id.in_([b.id for b in bookings])).order_by(Quote.created_at.desc())
        )).all()
        latest_q: dict[str, Quote] = {}
        for q in quotes:
            latest_q.setdefault(q.booking_id, q)

        lines.append("Shortlisted vendors:")
        for b in bookings:
            if b.venue_id:
                v = venues.get(b.venue_id)
                name, cat = (v.name if v else "a venue"), "venue"
            else:
                s = suppliers.get(b.supplier_id)
                name, cat = (s.name if s else "a supplier"), (s.category if s else "supplier")
            q = latest_q.get(b.id)
            quoted = f", quoted €{q.total_amount:,.0f}" if q else ""
            lines.append(f"  - {cat}: {name} (status {b.status}{quoted})")

    return "\n".join(lines)


@run_agent("concierge", "concierge_reply")
async def run_concierge(db: AsyncSession, wedding_id: str, message: str):
    """Answers a couple's question, grounded in their real budget/checklist/vendors."""
    model = model_for("concierge")  # not a planning agent → Flash (cheap + fast for chat)
    prompt_version = get_prompt_version(SYSTEM_INSTRUCTION)

    wedding = (await db.exec(select(Wedding).where(Wedding.id == wedding_id))).first()
    if not wedding:
        raise ValueError(f"Wedding not found: {wedding_id}")

    context = await _build_context(db, wedding)
    prompt = f"WEDDING CONTEXT:\n{context}\n\nCOUPLE'S QUESTION:\n{message}"

    client = get_client()
    logger.info(f"Invoking {model} for concierge reply (wedding {wedding_id})...")

    # Retry transient Gemini capacity errors so the live chat doesn't fail on a blip.
    response = None
    for attempt in range(3):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ConciergeReply,
                    temperature=0.4,
                ),
            )
            break
        except Exception as e:
            transient = any(t in str(e) for t in ("503", "UNAVAILABLE", "429"))
            if transient and attempt < 2:
                await asyncio.sleep(2)
                continue
            raise

    result_dict = json.loads(response.text)
    usage = response.usage_metadata
    api_calls = [{
        "provider": "google",
        "model": model,
        "tokens": {
            "input": usage.prompt_token_count if usage else 0,
            "output": usage.candidates_token_count if usage else 0,
        },
    }]

    reply = result_dict.get("reply", "")
    confidence = result_dict.get("confidence_score")
    return (
        {"reply": reply, "confidence_score": confidence, "rationale_summary": reply[:160]},
        confidence,
        model,
        prompt_version,
        api_calls,
    )
