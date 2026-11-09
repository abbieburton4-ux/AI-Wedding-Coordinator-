"""Check-before-send for every AI action (PD-008 follow-up 2, B49).

The first request for an AI action returns the cleaned text that would go to Gemini,
and sends nothing. The person reads it and clicks to send, which repeats the request
with ``approved_prompt`` set to that text. The run goes ahead only if the text it
would send now is exactly that text; ``send_prompt`` checks the same thing again
before the call.
"""
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from app.agents.privacy import PersonalDataInPrompt
from app.db.session import async_session_maker

NOT_CLEANED = ("We couldn't take every guest detail out of this text, so nothing was sent. "
               "Please remove names, emails and phone numbers and try again.")


class Approval(BaseModel):
    approved_prompt: Optional[str] = None


async def needs_review(agent, db, wedding_id: str, approved_prompt: Optional[str],
                       *args, **kwargs) -> Optional[dict]:
    """``None`` when the run may go ahead: it makes no model call, or the person approved
    exactly the text it would send. Otherwise the response that shows them the text
    (``changed`` when they approved an older version).

    The preview runs in its own session: it rolls back whatever the agent touched, and
    that would otherwise expire objects the caller's session still holds."""
    try:
        async with async_session_maker() as preview_db:
            out = await agent(preview_db, wedding_id, *args, preview_only=True, **kwargs)
    except PersonalDataInPrompt:
        raise HTTPException(status_code=422, detail=NOT_CLEANED)
    if not out["needs_review"]:
        return None
    if approved_prompt is not None and approved_prompt == out["preview"]:
        return None
    return {"needs_review": True, "preview": out["preview"],
            "changed": approved_prompt is not None}
