"""Wedding access levels (PD-002).

Every wedding endpoint goes through ``require_wedding_access`` so the rule lives in
one place: viewers can read, editors can also change things and run agents, and
owners can also manage who has access.
"""
import logging
from typing import Optional

from fastapi import HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ACCESS_LEVELS, User, Wedding, WeddingMember
from app.utils.email_match import UnsafeEmailError, normalise_email

logger = logging.getLogger(__name__)

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
    return member.level if member else None


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
        if minimum == "owner":
            raise HTTPException(status_code=403, detail="Only the people who manage access can do this")
        raise HTTPException(status_code=403, detail="Your access to this wedding is view only")
    return wedding


async def weddings_for_member(db: AsyncSession, user: User) -> list:
    """Weddings the user is on the access list for."""
    member_ids = select(WeddingMember.wedding_id).where(WeddingMember.user_id == user.id)
    result = await db.exec(select(Wedding).where(Wedding.id.in_(member_ids)))
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


UNSAFE_EMAIL = (
    "This email address has letters we can't check safely, such as a letter from another "
    "alphabet that looks like an English one. Use the address the couple added, typed in "
    "plain letters."
)


def bootstrap_emails() -> set:
    """The couple's own sign-in emails (ACCESS_BOOTSTRAP_EMAILS), normalised.

    An entry that can't be compared safely is left out, so it never matches anyone.
    """
    emails = set()
    for entry in settings.ACCESS_BOOTSTRAP_EMAILS.split(","):
        try:
            email = normalise_email(entry)
        except UnsafeEmailError:
            # The address itself stays out of the log (personal data).
            logger.warning("Ignored an ACCESS_BOOTSTRAP_EMAILS entry with non-ASCII characters")
            continue
        if email:
            emails.add(email)
    return emails


async def link_memberships(db: AsyncSession, user: User, email: str) -> bool:
    """Attach pending access-list rows for this verified email to the user.

    Returns True if the email is on any wedding's list. An address that can't be
    compared safely never links.
    """
    try:
        email = normalise_email(email)
    except UnsafeEmailError:
        return False
    if not email:
        return False
    result = await db.exec(select(WeddingMember).where(WeddingMember.email == email))
    rows = list(result.all())
    linked = await db.exec(
        select(WeddingMember.wedding_id).where(WeddingMember.user_id == user.id)
    )
    already_on = set(linked.all())
    for row in rows:
        # One row per person per wedding: if their address changed and the new one is
        # listed too, keep the row they already have rather than holding two levels.
        if row.user_id is None and row.wedding_id not in already_on:
            row.user_id = user.id
            db.add(row)
            already_on.add(row.wedding_id)
    return bool(rows)
