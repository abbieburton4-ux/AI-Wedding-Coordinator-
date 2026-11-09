"""The couple's own vendors, in the Vendors screen's sections (PD-012, B62).

Anyone on the access list can see them; only owners and editors add, edit or remove
one, or paste a vendor's reply for the AI to read. The status (looking, contacted,
booked, not selected) is whatever the couple set: nothing here or in any agent changes
it (rule 4), and nothing here contacts a vendor (rule 1).

Contact details are the vendor's business details. They're shown to the wedding
party, but they aren't logged, and they're never sent to the AI: only the pasted reply
is, after the couple have checked the cleaned text (PD-008).
"""
import datetime
import re
from typing import Dict, Iterable, List, Literal, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.extractor import run_vendor_reply_reader
from app.api.v1.access import require_wedding_access
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.review import MAX_PROMPT_CHARS, needs_review
from app.config import settings
from app.db.models import (
    NOT_SELECTED, CoupleVendor, CoupleVendorQuote, User, VENDOR_SECTIONS, utcnow,
)
from app.db.session import get_db
from app.utils.tasks import enqueue_agent_task

router = APIRouter()

NAME_MAX = 200
WEBSITE_MAX = 500
EMAIL_MAX = 254
PHONE_MAX = 40
NOTES_MAX = 2000

Section = Literal["venue", "food_drink", "flowers_decoration", "photo_video",
                  "entertainment", "hair_makeup", "transportation"]
Status = Literal["looking", "contacted", "booked", "not_selected"]

# A section's status is its furthest vendor's; "todo" when none is still in play.
STATUS_RANK = {"looking": 0, "contacted": 1, "booked": 2}
TODO = "todo"
SectionStatus = Literal["looking", "contacted", "booked", "todo"]

# No ? & = # % / either, so a saved address can't carry a mailto subject or body.
EMAIL_RE = re.compile(r"^[^@\s<>()\[\],;:\"?&=#%/]+@[^@\s<>()\[\],;:\"?&=#%/]+\.[^@\s<>()\[\],;:\".?&=#%/]+$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{3,30}(?:\s*(?:ext\.?|x)\s*\d{1,6})?$", re.IGNORECASE)


# --- Request bodies -------------------------------------------------------------------

class VendorIn(BaseModel):
    section: Section
    name: str = Field(max_length=NAME_MAX)
    website: Optional[str] = Field(default=None, max_length=WEBSITE_MAX)
    contact_name: Optional[str] = Field(default=None, max_length=NAME_MAX)
    email: Optional[str] = Field(default=None, max_length=EMAIL_MAX)
    phone: Optional[str] = Field(default=None, max_length=PHONE_MAX)
    status: Status = "looking"
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX)


class VendorPatch(BaseModel):
    """Only the fields sent change; an empty or null optional field is cleared."""
    section: Optional[Section] = None
    name: Optional[str] = Field(default=None, max_length=NAME_MAX)
    website: Optional[str] = Field(default=None, max_length=WEBSITE_MAX)
    contact_name: Optional[str] = Field(default=None, max_length=NAME_MAX)
    email: Optional[str] = Field(default=None, max_length=EMAIL_MAX)
    phone: Optional[str] = Field(default=None, max_length=PHONE_MAX)
    status: Optional[Status] = None
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX)


class ReplyIn(BaseModel):
    email_body: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    approved_prompt: Optional[str] = Field(default=None, max_length=MAX_PROMPT_CHARS)


# --- Responses ------------------------------------------------------------------------

class LineItemOut(BaseModel):
    item: str
    amount_cents: Optional[int]


class ReplyOut(BaseModel):
    """The AI's reading of the latest reply the couple pasted. Not a confirmed quote."""
    total_cents: Optional[int]
    currency: Optional[str]
    is_available: Optional[bool]
    line_items: List[LineItemOut]
    summary: Optional[str]
    read_at: datetime.datetime


class VendorOut(BaseModel):
    id: str
    section: str
    name: str
    website: Optional[str]
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    status: str
    notes: Optional[str]
    updated_at: datetime.datetime
    latest_reply: Optional[ReplyOut]


class VendorsOut(BaseModel):
    sections: List[str]
    vendors: List[VendorOut]
    # Each section's status for the summary: looking, contacted, booked or todo.
    section_status: Dict[str, SectionStatus]


# --- Cleaning -------------------------------------------------------------------------

def _name(text: Optional[str]) -> str:
    text = " ".join((text or "").split())
    if not text:
        raise HTTPException(status_code=422, detail="Please type the vendor's name")
    return text


def _optional(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = " ".join(text.split())
    return text or None


def _website(text: Optional[str]) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    parts = urlsplit(text)
    # A user part ("https://real.example@other.example") would disguise where it goes.
    if (parts.scheme.lower() not in ("http", "https") or not parts.hostname
            or "." not in parts.hostname or re.search(r"\s", text)
            or parts.username is not None or parts.password is not None):
        raise HTTPException(
            status_code=422,
            detail="Please give the website as a full address, like https://www.example.com")
    return text


def _email(text: Optional[str]) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    if not EMAIL_RE.match(text):
        raise HTTPException(status_code=422,
                            detail="That email address doesn't look right. Please check it")
    return text


def _phone(text: Optional[str]) -> Optional[str]:
    text = " ".join((text or "").split())
    if not text:
        return None
    if not PHONE_RE.match(text) or len(re.sub(r"\D", "", text)) < 3:
        raise HTTPException(
            status_code=422,
            detail="That phone number doesn't look right. Use digits, spaces, + ( ) - and ext")
    return text


def _notes(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = text.strip()
    return text or None


CLEANERS = {
    "name": _name, "website": _website, "contact_name": _optional, "email": _email,
    "phone": _phone, "notes": _notes,
}


# --- Helpers --------------------------------------------------------------------------

def set_status(row: CoupleVendor, value: str) -> None:
    # "Not selected" is a flag, so the stored status stays as it was (models.py).
    if value == NOT_SELECTED:
        row.not_selected = True
    else:
        row.status, row.not_selected = value, False


def section_status(statuses: Iterable[str]) -> str:
    """Ruled-out vendors don't count: a section with only those still needs a vendor."""
    in_play = [s for s in statuses if s in STATUS_RANK]
    return max(in_play, key=STATUS_RANK.__getitem__) if in_play else TODO


async def _vendor(db: AsyncSession, wedding_id: str, vendor_id: str) -> CoupleVendor:
    row = (await db.exec(select(CoupleVendor).where(
        CoupleVendor.id == vendor_id, CoupleVendor.wedding_id == wedding_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="That vendor isn't on your list")
    return row


def _reply_out(q: Optional[CoupleVendorQuote]) -> Optional[ReplyOut]:
    if q is None:
        return None
    items = [LineItemOut(item=str(li.get("item", "")), amount_cents=li.get("amount_cents"))
             for li in (q.line_items or []) if isinstance(li, dict)]
    return ReplyOut(total_cents=q.total_cents, currency=q.currency,
                    is_available=q.is_available, line_items=items, summary=q.summary,
                    read_at=q.created_at)


def _out(row: CoupleVendor, latest: Optional[CoupleVendorQuote]) -> VendorOut:
    return VendorOut(
        id=row.id, section=row.section, name=row.name, website=row.website,
        contact_name=row.contact_name, email=row.email, phone=row.phone,
        status=row.shown_status,
        notes=row.notes, updated_at=row.updated_at, latest_reply=_reply_out(latest),
    )


async def _latest_replies(db: AsyncSession, vendor_ids: list) -> dict:
    if not vendor_ids:
        return {}
    rows = (await db.exec(
        select(CoupleVendorQuote).where(CoupleVendorQuote.vendor_id.in_(vendor_ids))
        .order_by(CoupleVendorQuote.created_at.desc(), CoupleVendorQuote.id)
    )).all()
    latest = {}
    for q in rows:
        latest.setdefault(q.vendor_id, q)
    return latest


# --- Routes ---------------------------------------------------------------------------

@router.get("/{wedding_id}/vendors", response_model=VendorsOut)
async def list_vendors(
    wedding_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "viewer")
    rows = (await db.exec(
        select(CoupleVendor).where(CoupleVendor.wedding_id == wedding_id)
        .order_by(CoupleVendor.created_at, CoupleVendor.id)
    )).all()
    latest = await _latest_replies(db, [r.id for r in rows])
    return VendorsOut(
        sections=list(VENDOR_SECTIONS),
        vendors=[_out(r, latest.get(r.id)) for r in rows],
        section_status={sec: section_status(r.shown_status for r in rows if r.section == sec)
                        for sec in VENDOR_SECTIONS},
    )


@router.post("/{wedding_id}/vendors", status_code=status.HTTP_201_CREATED,
             response_model=VendorOut)
async def add_vendor(
    wedding_id: str, payload: VendorIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "editor")
    fields = {k: CLEANERS[k](getattr(payload, k)) for k in CLEANERS}
    row = CoupleVendor(wedding_id=wedding_id, section=payload.section, **fields)
    set_status(row, payload.status)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row, None)


@router.patch("/{wedding_id}/vendors/{vendor_id}", response_model=VendorOut)
async def edit_vendor(
    wedding_id: str, vendor_id: str, payload: VendorPatch,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "editor")
    row = await _vendor(db, wedding_id, vendor_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key in CLEANERS:
            setattr(row, key, CLEANERS[key](value))
        elif value is None:
            raise HTTPException(status_code=422, detail=f"Please choose a {key}")
        elif key == "status":
            set_status(row, value)
        else:
            setattr(row, key, value)
    row.updated_at = utcnow()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    latest = await _latest_replies(db, [row.id])
    return _out(row, latest.get(row.id))


@router.delete("/{wedding_id}/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vendor(
    wedding_id: str, vendor_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_wedding_access(db, wedding_id, current_user, "editor")
    row = await _vendor(db, wedding_id, vendor_id)
    for q in (await db.exec(select(CoupleVendorQuote).where(
            CoupleVendorQuote.vendor_id == row.id))).all():
        await db.delete(q)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{wedding_id}/vendors/{vendor_id}/reply", status_code=status.HTTP_202_ACCEPTED)
async def read_vendor_reply(
    wedding_id: str, vendor_id: str, payload: ReplyIn,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """The AI reads the price and availability from a reply the couple pasted.

    The first call returns the cleaned text that would go to the AI and sends nothing;
    the couple send it by repeating the call with that text as ``approved_prompt``
    (PD-008). The vendor's status is never changed."""
    await require_wedding_access(db, wedding_id, current_user, "editor")
    await _vendor(db, wedding_id, vendor_id)
    review = await needs_review(run_vendor_reply_reader, db, wedding_id,
                                payload.approved_prompt, payload.email_body,
                                vendor_id=vendor_id)
    if review:
        return review
    enqueued = await enqueue_agent_task("vendor-reply", {
        "wedding_id": wedding_id,
        "vendor_id": vendor_id,
        "email_body": payload.email_body,
        "approved_prompt": payload.approved_prompt,
    })
    if not enqueued:
        raise HTTPException(status_code=500, detail="The reply couldn't be sent to the AI")
    return {"status": "completed" if settings.DIRECT_AGENT_EXECUTION else "pending"}
