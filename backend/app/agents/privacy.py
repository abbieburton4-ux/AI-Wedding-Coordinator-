"""Keeps guest and wedding-party personal data away from Gemini (PD-008, B49).

On Gemini's free tier Google may use what it's sent and human reviewers may read it,
so the couple decided the model never receives guest names, contact details or
dietary notes; counts and categories ("12 vegetarian") are fine.

``send_prompt`` is the only place in the app that calls the model. Before every
call it removes, from the prompt text:
- the names, emails and phone numbers of the wedding's guests, of everyone on
  its access list (the couple and their party) and of the contact people the couple
  saved for their vendors, with or without accents and in any
  case (name parts that are also everyday words, like "Will", only as written);
- guests' dietary notes, word for word (punctuation aside), unless the note is one
  of the plain categories in ``DIETARY_CATEGORIES`` ("vegan", "gluten free");
- anything shaped like an email address or a phone number.

Only names the app knows can be removed. A name that isn't on the guest list or the
access list (say, a vendor mentioning someone new) can't be reliably spotted. So
(PD-008 follow-up 2) nothing is sent until the person has seen the cleaned text and
clicked to send it: the first call of an agent is a preview that returns that text
and sends nothing, and the real call sends only if its cleaned text is exactly the
text the person approved. ``scrub`` applies the same removal to the decision log.
"""
import re
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models import CoupleVendor, Guest, User, Wedding, WeddingMember

NAME_MARK = "[name]"
EMAIL_MARK = "[email]"
PHONE_MARK = "[phone]"
DIETARY_MARK = "[dietary note]"

# The look-behind keeps this linear on long runs of word characters with no "@".
EMAIL_RE = re.compile(r"(?<![\w.+'-])[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
# International (+353 87 ...), trunk-prefixed (087 ..., (01) ...), US-style
# (555-123-4567) and bare 10-digit US numbers. Prices and dates survive.
PHONE_RE = re.compile(
    r"(?:\+|\(?\b0)\d[\d\s().-]{6,}\d"
    r"|\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"
    r"|\b[2-9]\d{9}\b"
)
MIN_PHONE_DIGITS = 9
# A JSON escape such as á would hide an accented name from the checks.
UNICODE_ESCAPE_RE = re.compile(r"\\u[0-9a-fA-F]{4}")
# Dietary notes that are only a category may be sent; anything else describes
# someone's health and is removed word for word.
DIETARY_CATEGORIES = {
    "vegetarian", "vegan", "pescatarian", "gluten free", "gluten-free", "dairy free",
    "dairy-free", "nut free", "nut-free", "nut allergy", "halal", "kosher", "none",
    "no restrictions", "coeliac", "celiac",
}
# Name parts that are also everyday words match only as written ("Will", not "will");
# every other name part matches in any case ("ottoline", "OTTOLINE").
COMMON_WORDS = {
    "will", "may", "june", "april", "august", "rose", "grace", "hope", "joy", "faith",
    "mark", "bill", "art", "sky", "dawn", "summer", "autumn", "holly", "ivy", "lily",
    "daisy", "violet", "iris", "pearl", "ruby", "amber", "olive", "jade", "hazel",
    "rich", "frank", "earnest", "chase", "hunter", "mason", "carter", "cook", "baker",
    "page", "price", "rice", "young", "king", "white", "black", "brown", "green", "gray",
    "grey", "long", "small", "hall", "wood", "hill", "field", "lane", "ford", "bell",
    "love", "sunny", "honey", "star", "river", "brook", "glen", "dale", "clay", "stone",
    "max", "sue", "pat", "don", "ray", "rob", "jack", "nick", "clare", "kerry", "cork",
    "down",
}


def normalise(text: str) -> str:
    """One form for matching: NFC, straight apostrophes, no zero-width characters."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"[​-‍⁠﻿]", "", text)


def _unaccented(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return unicodedata.normalize(
        "NFC", "".join(c for c in decomposed if not unicodedata.combining(c)))


@dataclass
class PersonalTerms:
    names: set = field(default_factory=set)
    emails: set = field(default_factory=set)
    phone_digits: set = field(default_factory=set)
    dietary_notes: set = field(default_factory=set)
    # Vendors' contact people (B62): matched only as the whole name, as written, since
    # the field may hold a role ("Wedding Coordinator") made of everyday words.
    contact_names: set = field(default_factory=set)
    _patterns: list = field(default=None, repr=False)

    def patterns(self) -> list:
        """(kind, mark, pattern) in the order they're applied, compiled once."""
        if self._patterns is None:
            out = []
            # Sorted, so the same details always give the same cleaned text: a preview
            # and the send it approves must match exactly.
            for note in sorted(self.dietary_notes, key=lambda n: (-len(n), n)):
                out.append(("dietary note", DIETARY_MARK, _dietary_pattern(note)))
            out.append(("email", EMAIL_MARK, EMAIL_RE))
            for email in sorted(self.emails):
                out.append(("email", EMAIL_MARK, re.compile(re.escape(email), re.IGNORECASE)))
            for digits in sorted(self.phone_digits):
                for tail in sorted({digits, digits[-9:]}):
                    out.append(("phone", PHONE_MARK, re.compile(
                        r"(?<!\d)" + r"[\s().-]*".join(tail) + r"(?!\d)")))
            out.append(("phone", PHONE_MARK, PHONE_RE))
            # Longest first, so a full name goes before its parts.
            for name in sorted(self.names, key=lambda n: (-len(n), n)):
                out.append(("name", NAME_MARK, _name_pattern(name)))
            for name in sorted(self.contact_names, key=lambda n: (-len(n), n)):
                words = r"\s+".join(re.escape(w) for w in name.split())
                out.append(("name", NAME_MARK, re.compile(r"(?<!\w)" + words + r"(?!\w)")))
            self._patterns = out
        return self._patterns


def _name_parts(name: str) -> set:
    """The full name and each capitalised part (hyphenated parts too), with and
    without accents, so "Dear Mary" and "Siobhan" are caught. Lower-case particles
    ("de", "van") and initials are left alone."""
    name = " ".join(normalise(name or "").split())
    if not name:
        return set()
    parts = {name}
    for part in re.split(r"[\s&,/+]+", name):
        part = part.strip(".()\"")
        for piece in [part] + (part.split("-") if "-" in part else []):
            if len(piece) >= 2 and piece[0].isupper():
                parts.add(piece)
    return parts | {_unaccented(p) for p in parts}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


async def load_personal_terms(db: AsyncSession, wedding_id: str) -> PersonalTerms:
    """The personal details the app holds for this wedding's guests and party."""
    terms = PersonalTerms()

    def add_person(name, email, phone):
        terms.names |= _name_parts(name)
        if email and email.strip():
            terms.emails.add(normalise(email.strip().lower()))
        if len(_digits(phone)) >= 6:
            terms.phone_digits.add(_digits(phone))

    for g in (await db.exec(select(Guest).where(Guest.wedding_id == wedding_id))).all():
        add_person(g.name, g.email, g.phone)
        note = " ".join(normalise(g.dietary or "").split())
        if note and note.lower() not in DIETARY_CATEGORIES:
            terms.dietary_notes |= {note, _unaccented(note)}

    members = (await db.exec(
        select(WeddingMember).where(WeddingMember.wedding_id == wedding_id)
    )).all()
    user_ids = {m.user_id for m in members if m.user_id}
    for m in members:
        add_person(None, m.email, None)
    wedding = (await db.exec(select(Wedding).where(Wedding.id == wedding_id))).first()
    if wedding:
        user_ids |= {u for u in (wedding.couple_user_id, wedding.planner_user_id) if u}
    if user_ids:
        for u in (await db.exec(select(User).where(User.id.in_(user_ids)))).all():
            add_person(u.name, u.email, u.phone)

    # The couple's vendors' contact people (B62): business details, but still kept out
    # of prompts and logs, for every agent. Only the whole contact name, as written, is
    # removed, and it isn't checked against the app's own instructions (``_whole_names``
    # leaves it out), so a role such as "Wedding Coordinator" never blocks an AI feature.
    vendors = (await db.exec(
        select(CoupleVendor).where(CoupleVendor.wedding_id == wedding_id)
    )).all()
    for v in vendors:
        add_person(None, v.email, v.phone)
        contact = " ".join(normalise(v.contact_name or "").split())
        if len(contact) >= 2:
            terms.contact_names |= {contact, _unaccented(contact)}
    return terms


def _name_pattern(name: str) -> re.Pattern:
    words = r"\s+".join(re.escape(w) for w in name.split())
    as_written = " " not in name and name.lower() in COMMON_WORDS
    return re.compile(r"(?<!\w)" + words + r"(?!\w)", 0 if as_written else re.IGNORECASE)


def _dietary_pattern(note: str) -> re.Pattern:
    """The note's words in order, whatever punctuation or spacing sits between them."""
    words = [w for w in re.split(r"[\W_]+", note) if w]
    return re.compile(r"(?<!\w)" + r"[\W_]+".join(map(re.escape, words)) + r"(?!\w)",
                      re.IGNORECASE)


def _counts(kind: str, match: re.Match) -> bool:
    # Generic phone-shaped runs only count as phones with enough digits.
    return kind != "phone" or len(_digits(match.group(0))) >= MIN_PHONE_DIGITS \
        or match.re is not PHONE_RE


def redact(text: str, terms: PersonalTerms, generic: bool = True) -> str:
    """Text with every known personal detail replaced, and (``generic``) anything
    shaped like an email or phone number."""
    if not isinstance(text, str) or not text:
        return text
    text = normalise(text)
    for kind, mark, pattern in terms.patterns():
        if not generic and pattern in (EMAIL_RE, PHONE_RE):
            continue
        text = pattern.sub(lambda m: mark if _counts(kind, m) else m.group(0), text)
    return text


def find_personal(text: str, terms: PersonalTerms) -> list:
    """The kinds of personal detail still in ``text`` (empty when clean)."""
    if not isinstance(text, str):
        return []
    found = ["hidden characters"] if UNICODE_ESCAPE_RE.search(text) else []
    text = normalise(text)
    for kind, _mark, pattern in terms.patterns():
        if kind not in found and any(_counts(kind, m) for m in pattern.finditer(text)):
            found.append(kind)
    return found


class PersonalDataInPrompt(RuntimeError):
    """A prompt still held personal data after redaction, so it wasn't sent."""


class PromptNeedsReview(Exception):
    """Raised by ``send_prompt`` during a preview: carries the cleaned text that would
    be sent. Nothing was sent."""

    def __init__(self, preview: str):
        super().__init__("Waiting for the person to check the text before it's sent.")
        self.preview = preview


class PromptNotApproved(RuntimeError):
    """The cleaned prompt wasn't the text the person approved (or none was), so it
    wasn't sent."""


# Set by ``run_agent`` for one agent run: preview mode, or the text the person approved.
_previewing: ContextVar[bool] = ContextVar("prompt_previewing", default=False)
_approved: ContextVar[Optional[str]] = ContextVar("prompt_approved", default=None)


def scrub(value, terms: PersonalTerms, generic: bool = True):
    """A copy of a decision-log value with personal details removed. ``generic=False``
    removes only the details the app holds, leaving other emails and numbers (a
    vendor's, in a draft inquiry the couple will send)."""
    if isinstance(value, str):
        return redact(value, terms, generic)
    if isinstance(value, dict):
        return {k: scrub(v, terms, generic) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v, terms, generic) for v in value]
    return value


def _whole_names(terms: PersonalTerms) -> PersonalTerms:
    """The terms for checking the app's own fixed instructions: whole names only, not
    single name parts, which are often ordinary words there ("Mark is_available",
    "Irish", "the couple's"). Contacts and dietary notes are all still checked."""
    return PersonalTerms(names={n for n in terms.names if " " in n}, emails=terms.emails,
                         phone_digits=terms.phone_digits, dietary_notes=terms.dietary_notes)


async def send_prompt(db: AsyncSession, wedding_id: str, client, *, model, contents, config):
    """Calls Gemini with personal details removed from the prompt, once the person has
    approved that exact cleaned text.

    Refuses to send (raises ``PersonalDataInPrompt``, which the orchestrator logs as an
    error) if a known detail, or a \\u escape that could hide one, is still there.
    In a preview it raises ``PromptNeedsReview`` with the cleaned text instead of
    sending. Otherwise it sends only if the cleaned text equals the approved text, and
    raises ``PromptNotApproved`` if it doesn't.
    """
    if not isinstance(contents, str):
        raise PersonalDataInPrompt("Only plain-text prompts can be checked, so none other is sent.")
    terms = await load_personal_terms(db, wedding_id)
    clean = redact(contents, terms)
    instruction = getattr(config, "system_instruction", None)
    leftovers = find_personal(clean, terms) + find_personal(instruction, _whole_names(terms))
    if leftovers:
        raise PersonalDataInPrompt(f"Prompt not sent: it still held a {leftovers[0]}.")
    if _previewing.get():
        raise PromptNeedsReview(clean)
    approved = _approved.get()
    if approved is None or approved != clean:
        raise PromptNotApproved("Prompt not sent: it wasn't the text the person checked.")
    return await client.aio.models.generate_content(model=model, contents=approved, config=config)
