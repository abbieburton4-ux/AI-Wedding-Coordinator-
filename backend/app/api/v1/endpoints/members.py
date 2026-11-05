"""The wedding's access list, managed by its owners (PD-002 step 2, backlog B22).

Only owners can see or change the list. Adding someone never contacts them (hard
rule 1): the owner tells the person themselves, and the row links to that person's
account when they sign in with the same email, verified.
"""
import re
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.v1.access import require_wedding_access, wedding_level
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import User, WeddingMember
from app.db.session import get_db
from app.utils.email_match import UnsafeEmailError, normalise_email

router = APIRouter()

# Owners are set up with the wedding (the couple). The API adds and switches
# people between these two levels only; it never makes someone an owner (PD-002).
AssignableLevel = Literal["viewer", "editor"]

# Checked on the normalised (ASCII-only) address; see app.utils.email_match.
_EMAIL_RE = re.compile(r"^[!-?A-~]+@[A-Za-z0-9.-]+\.[A-Za-z0-9-]+$")

ALREADY_LISTED = "That email already has access"

UNSAFE_NEW_EMAIL = (
    "That address has letters we can't check safely, such as a letter from another "
    "alphabet that looks like an English one. Type it again in plain letters."
)

OWNER_PROTECTED = (
    "People who manage access can't be removed or changed in the app. If that ever "
    "needs to change, ask the team to do it for you."
)


class MemberOut(BaseModel):
    id: str
    email: str
    level: str
    signed_in: bool


class MemberCreate(BaseModel):
    email: str = Field(max_length=254)
    level: AssignableLevel


class MemberUpdate(BaseModel):
    level: AssignableLevel


class MyAccess(BaseModel):
    level: str


def _out(row: WeddingMember) -> MemberOut:
    return MemberOut(id=row.id, email=row.email, level=row.level, signed_in=row.user_id is not None)


async def _member(db: AsyncSession, wedding_id: str, member_id: str) -> WeddingMember:
    result = await db.exec(
        select(WeddingMember).where(
            WeddingMember.id == member_id, WeddingMember.wedding_id == wedding_id
        )
        # Locked so a team change to this row (manage_access.py) can't land between
        # the owner check and the write.
        .with_for_update()
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="That person isn't on this wedding's list")
    return row


def _refuse_if_owner(row: WeddingMember) -> None:
    """Owner rows are fixed in the app (PD-002 note, 2026-11-05).

    Neither partner can remove or demote the other, nor themselves, so the wedding
    always keeps both people who manage access. The team can still change an owner
    with manage_access.py when the couple ask.
    """
    if row.level == "owner":
        raise HTTPException(status_code=409, detail=OWNER_PROTECTED)


@router.get("/{wedding_id}/my-access", response_model=MyAccess)
async def my_access(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The signed-in person's own level, so the app knows which screens to offer."""
    wedding = await require_wedding_access(db, wedding_id, current_user, "viewer")
    return MyAccess(level=await wedding_level(db, wedding, current_user))


@router.get("/{wedding_id}/members", response_model=List[MemberOut])
async def list_members(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "owner")
    result = await db.exec(
        select(WeddingMember)
        .where(WeddingMember.wedding_id == wedding_id)
        .order_by(WeddingMember.created_at, WeddingMember.email)
    )
    return [_out(row) for row in result.all()]


@router.post("/{wedding_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    wedding_id: str,
    payload: MemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds an email to the list. Sends nothing: the owner lets the person know."""
    await require_wedding_access(db, wedding_id, current_user, "owner")
    try:
        email = normalise_email(payload.email)
    except UnsafeEmailError:
        raise HTTPException(status_code=422, detail=UNSAFE_NEW_EMAIL)
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="That doesn't look like an email address")
    existing = await db.exec(
        select(WeddingMember.id).where(
            WeddingMember.wedding_id == wedding_id, WeddingMember.email == email
        )
    )
    if existing.first() is not None:
        raise HTTPException(status_code=409, detail=ALREADY_LISTED)
    # Left unlinked: it attaches to an account only at a verified sign-in with this
    # email (access.link_memberships), so nobody can claim it with an unconfirmed one.
    row = WeddingMember(wedding_id=wedding_id, email=email, level=payload.level)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        # Two owners adding the same address at once: the unique constraint catches it.
        await db.rollback()
        raise HTTPException(status_code=409, detail=ALREADY_LISTED)
    await db.refresh(row)
    return _out(row)


@router.patch("/{wedding_id}/members/{member_id}", response_model=MemberOut)
async def change_member_level(
    wedding_id: str,
    member_id: str,
    payload: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "owner")
    row = await _member(db, wedding_id, member_id)
    _refuse_if_owner(row)
    if row.level != payload.level:
        row.level = payload.level
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return _out(row)


@router.delete("/{wedding_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    wedding_id: str,
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "owner")
    row = await _member(db, wedding_id, member_id)
    _refuse_if_owner(row)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
