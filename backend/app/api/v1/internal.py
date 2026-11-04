"""Shared-secret checks for routes only our own services or providers may call.

Each check passes freely in DEVELOPMENT_MODE (local throwaway setups). Everywhere
else it fails closed: if the secret isn't configured, every call is refused.
"""
import hmac
from typing import Optional

from fastapi import HTTPException, Request

from app.config import settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def _matches(given: Optional[str], expected: Optional[str]) -> bool:
    return bool(expected) and bool(given) and hmac.compare_digest(given, expected)


def internal_headers() -> dict:
    """Headers our task dispatcher adds when it calls the worker routes."""
    if settings.INTERNAL_TASKS_SECRET:
        return {INTERNAL_TOKEN_HEADER: settings.INTERNAL_TASKS_SECRET}
    return {}


async def require_internal_caller(request: Request) -> None:
    """Dependency for the /tasks worker routes, which run agents and change data."""
    if settings.DEVELOPMENT_MODE:
        return
    if not _matches(request.headers.get(INTERNAL_TOKEN_HEADER), settings.INTERNAL_TASKS_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")


def require_inbound_email_token(request: Request) -> None:
    """The inbound-email webhook URL must carry ?token=<INBOUND_EMAIL_SECRET>."""
    if settings.DEVELOPMENT_MODE:
        return
    if not _matches(request.query_params.get("token"), settings.INBOUND_EMAIL_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
