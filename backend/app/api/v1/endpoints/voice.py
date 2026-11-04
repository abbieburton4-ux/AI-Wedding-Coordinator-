"""Server-side credential broker for the ElevenLabs "Aurelia" voice agent.

The browser cannot be trusted with the ElevenLabs API key, so it never sees it.
Instead the signed-in couple/planner calls GET /voice/token; we exchange our
secret key for a short-lived WebRTC conversation token scoped to the Aurelia
agent and hand only that back to the client. Auth is required so this endpoint
can't be used as an open proxy that burns ElevenLabs quota.
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.db.models import User
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

ELEVENLABS_TOKEN_URL = "https://api.elevenlabs.io/v1/convai/conversation/token"


@router.get("/token")
async def get_conversation_token(
    current_user: User = Depends(get_current_user),
):
    """Mint a WebRTC conversation token for the Aurelia voice agent.

    Returns {"token": "...", "agentId": "..."}. The agent id is public (it ships
    in the client SDK call); only the API key is secret and stays server-side.
    """
    if not settings.ELEVENLABS_API_KEY:
        # Misconfiguration, not a client error — surface a 503 so the UI can hide
        # the voice option rather than showing a generic failure.
        raise HTTPException(
            status_code=503,
            detail="Voice agent is not configured on this server.",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                ELEVENLABS_TOKEN_URL,
                params={"agent_id": settings.ELEVENLABS_AGENT_ID},
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
    except httpx.HTTPError:
        logger.exception("Failed to reach ElevenLabs for a conversation token")
        raise HTTPException(status_code=502, detail="Voice agent is briefly unavailable.")

    if response.status_code != 200:
        logger.error(
            "ElevenLabs token request failed: %s %s", response.status_code, response.text
        )
        raise HTTPException(status_code=502, detail="Voice agent is briefly unavailable.")

    token = response.json().get("token")
    if not token:
        logger.error("ElevenLabs token response missing 'token': %s", response.text)
        raise HTTPException(status_code=502, detail="Voice agent is briefly unavailable.")

    return {"token": token, "agentId": settings.ELEVENLABS_AGENT_ID}
