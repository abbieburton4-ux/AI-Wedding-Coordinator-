"""Check-before-send for every AI action (PD-008 follow-up 2, B49).

The first request for an AI action returns the cleaned text that would go to Gemini,
and sends nothing. The person reads it and clicks to send, which repeats the request
with ``approved_prompt`` set to that text. The run goes ahead only if the text it
would send now is exactly that text; ``send_prompt`` checks the same thing again
before the call. Approval means "this exact text"; the click itself happens in the
browser.
"""
import logging
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agents.privacy import PersonalDataInPrompt
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

# Long enough for a matcher prompt with the catalogue; bounds what a paste can queue.
MAX_PROMPT_CHARS = 100_000

NOT_CLEANED = ("We couldn't take every personal detail out of this, so nothing was sent. "
               "If you typed or pasted names, emails or phone numbers, remove them and try "
               "again. If that doesn't help, let the team know.")
PREVIEW_FAILED = "We couldn't get this ready to check just now, so nothing was sent. Please try again."


class Approval(BaseModel):
    approved_prompt: Optional[str] = Field(default=None, max_length=MAX_PROMPT_CHARS)


async def needs_review(agent, db, wedding_id: str, approved_prompt: Optional[str],
                       *args, **kwargs) -> Optional[dict]:
    """``None`` when the run may go ahead: it makes no model call, or the person approved
    exactly the text it would send. Otherwise the response that shows them the text
    (``changed`` when they approved an older version).

    The preview runs in its own session: it rolls back whatever the agent touched, and
    that would otherwise expire objects the caller's session still holds. Previews
    write no decision row, so a failure is logged here, by kind only."""
    try:
        async with async_session_maker() as preview_db:
            out = await agent(preview_db, wedding_id, *args, preview_only=True, **kwargs)
    except PersonalDataInPrompt:
        raise HTTPException(status_code=422, detail=NOT_CLEANED)
    except Exception as exc:
        logger.error("Preview for %s failed: %s", getattr(agent, "__name__", "agent"),
                     type(exc).__name__)
        raise HTTPException(status_code=502, detail=PREVIEW_FAILED) from None
    if not out["needs_review"]:
        return None
    if approved_prompt is not None and approved_prompt == out["preview"]:
        return None
    return {"needs_review": True, "preview": out["preview"],
            "changed": approved_prompt is not None}
