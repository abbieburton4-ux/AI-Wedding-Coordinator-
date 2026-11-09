"""The switch for Aurelia, the in-app assistant (typed chat and voice).

PD-010 turned Aurelia off. The code stays so it can come back by setting
``ASSISTANT_ENABLED``; until then the routes refuse before anything is sent to
Gemini or ElevenLabs.
"""
from fastapi import HTTPException

from app.config import settings

ASSISTANT_OFF_DETAIL = "Aurelia, the assistant, is turned off for this wedding."


def require_assistant_enabled() -> None:
    if not settings.ASSISTANT_ENABLED:
        raise HTTPException(status_code=403, detail=ASSISTANT_OFF_DETAIL)
