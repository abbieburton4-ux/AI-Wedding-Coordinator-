"""Request-bound agent execution: no detached tasks or false queue acknowledgments."""
from sqlmodel import select

from app.db.models import Booking
from app.db.session import async_session_maker
from app.agents.planner import run_intake_planner
from app.agents.matcher import run_venue_matcher, run_supplier_matcher
from app.agents.extractor import run_quote_extractor, run_vendor_reply_reader


async def execute_agent_task(task_name: str, payload: dict) -> dict:
    # Match the worker's session isolation and the existing run_agent contract.
    # The text the couple checked and clicked to send, if any (PD-008).
    approval = ({"approved_prompt": payload["approved_prompt"]}
                if payload.get("approved_prompt") is not None else {})
    async with async_session_maker() as db:
        if task_name == "intake-planner":
            return await run_intake_planner(
                db, payload["wedding_id"], force=payload.get("force", False),
                trigger="couple_action", **approval,
            )
        if task_name == "venue-matcher":
            return await run_venue_matcher(
                db, payload["wedding_id"], trigger="couple_action", **approval,
            )
        if task_name == "supplier-matcher":
            return await run_supplier_matcher(
                db, payload["wedding_id"], payload["category"], trigger="couple_action",
                **approval,
            )
        if task_name == "quote-extractor":
            booking = (await db.exec(
                select(Booking).where(Booking.id == payload["booking_id"])
            )).first()
            if not booking:
                raise ValueError("Booking not found.")
            return await run_quote_extractor(
                db, str(booking.wedding_id), booking.id, payload["email_body"],
                trigger="supplier_response", booking_id=booking.id, **approval,
            )
        if task_name == "vendor-reply":
            return await run_vendor_reply_reader(
                db, payload["wedding_id"], payload["email_body"],
                vendor_id=payload["vendor_id"], trigger="supplier_response", **approval,
            )
        raise ValueError("Unsupported agent task.")
