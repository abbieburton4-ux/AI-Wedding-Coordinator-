"""Wedding access levels (PD-002).

Every wedding endpoint goes through ``require_wedding_access`` so the rule lives in
one place: viewers can read, editors can also change things and run agents, and
owners can also manage who has access.
"""
from typing import Optional

from fastapi import HTTPException
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ACCESS_LEVELS, User, Wedding, WeddingMember

_RANK = {level: i for i, level in enumerate(ACCESS_LEVELS)}


async def wedding_level(db: AsyncSession, wedding: Wedding, user: User) -> Optional[str]:
    """The user's access level on this wedding, or None.

    The access list is the only source of truth, so removing or demoting someone
    takes effect, including the person who created the wedding.
    """
    result = await db.exec(
        select(WeddingMember).where(
            WeddingMember.wedding_id == wedding.id,
            WeddingMember.user_id == user.id,
        )
    )
    member = result.first()
    if member:
        return member.level
    # Legacy SaaS planner link: kept working, but never above editor.
    if wedding.planner_user_id and wedding.planner_user_id == user.id:
        return "editor"
    return None


async def require_wedding_access(
    db: AsyncSession, wedding_id: str, user: User, minimum: str = "viewer"
) -> Wedding:
    """Load the wedding, or raise 404/403 if it's missing or the user's level is too low."""
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    level = await wedding_level(db, wedding, user)
    if level is None:
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")
    if _RANK[level] < _RANK[minimum]:
        raise HTTPException(status_code=403, detail="Your access to this wedding is view only")
    return wedding


async def weddings_for_member(db: AsyncSession, user: User) -> list:
    """Weddings the user is on the access list for (plus legacy planner links)."""
    member_ids = select(WeddingMember.wedding_id).where(WeddingMember.user_id == user.id)
    result = await db.exec(
        select(Wedding).where(
            or_(Wedding.id.in_(member_ids), Wedding.planner_user_id == user.id)
        )
    )
    return list(result.all())


async def has_level_anywhere(db: AsyncSession, user: User, minimum: str) -> bool:
    """Whether the user has at least ``minimum`` on any wedding's access list."""
    allowed = [lvl for lvl in ACCESS_LEVELS if _RANK[lvl] >= _RANK[minimum]]
    result = await db.exec(
        select(WeddingMember.id).where(
            WeddingMember.user_id == user.id, WeddingMember.level.in_(allowed)
        )
    )
    return result.first() is not None


def normalise_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def bootstrap_emails() -> set:
    """The couple's own sign-in emails (ACCESS_BOOTSTRAP_EMAILS), normalised."""
    return {normalise_email(e) for e in settings.ACCESS_BOOTSTRAP_EMAILS.split(",") if e.strip()}


async def link_memberships(db: AsyncSession, user: User, email: str) -> bool:
    """Attach pending access-list rows for this verified email to the user.

    Returns True if the email is on any wedding's list.
    """
    email = normalise_email(email)
    if not email:
        return False
    result = await db.exec(select(WeddingMember).where(WeddingMember.email == email))
    rows = list(result.all())
    for row in rows:
        if row.user_id is None:
            row.user_id = user.id
            db.add(row)
    return bool(rows)
