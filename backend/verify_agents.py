import os
import sys
import json
import re
import asyncio
import uuid
from unittest.mock import patch, MagicMock

# Override database URLs to use a local test SQLite DB
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./verify_agents_test.db"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///./verify_agents_test.db"
os.environ["DEVELOPMENT_MODE"] = "True"
os.environ["ALLOW_MOCK_AUTH"] = "True"
os.environ["GEMINI_API_KEY"] = "mock_key"

# Add current folder to path
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlmodel import SQLModel, select
from app.db.session import sync_engine, async_session_maker
from app.db.models import (
    Wedding, User, BudgetLine, TimelineItem, ChecklistTask, Booking, Quote, AgentDecisionLog,
)
from app.db.seed import seed_database

# Agent Imports
from app.agents.planner import run_intake_planner
from app.agents.matcher import run_venue_matcher, run_supplier_matcher
from app.agents.extractor import run_quote_extractor, run_vendor_reply_reader

# Helper classes for Mocking Gemini Response
class MockUsageMetadata:
    def __init__(self, prompt_token_count=15, candidates_token_count=25):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count

class MockResponse:
    def __init__(self, text, prompt_tokens=15, output_tokens=25):
        self.text = text
        self.usage_metadata = MockUsageMetadata(prompt_tokens, output_tokens)

async def approved(agent, db, wedding_id, *args, **kwargs):
    """Runs an agent the way the app does once the person has clicked send (PD-008):
    a preview first, then the run with exactly the previewed text."""
    check = await agent(db, wedding_id, *args, preview_only=True, **kwargs)
    approval = {"approved_prompt": check["preview"]} if check["needs_review"] else {}
    return await agent(db, wedding_id, *args, **approval, **kwargs)


async def run_async_verification():
    print("--- STARTING ASYNC AGENT LOGIC VERIFICATION ---")
    
    # 1. Setup Database
    print("1. Creating database tables in SQLite...")
    SQLModel.metadata.drop_all(sync_engine)
    SQLModel.metadata.create_all(sync_engine)
    
    print("2. Seeding database...")
    seed_database()
    
    # Create a mock Google GenAI Client
    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()
    mock_aio.models = mock_models
    mock_client.aio = mock_aio

    # Patch get_client in all agent modules to return our mock client
    with patch("app.agents.planner.get_client", return_value=mock_client), \
         patch("app.agents.matcher.get_client", return_value=mock_client), \
         patch("app.agents.extractor.get_client", return_value=mock_client):
        async with async_session_maker() as db:
            
            # --- TEST 1: INTAKE PLANNER SUCCESS ---
            print("\nTEST 1: Running Intake Planner (Success Path)...")
            planner_response = {
                "is_budget_realistic": True,
                "guardrail_warning": "",
                "budget_lines": [
                    {"category": "venue", "allocated_amount": 15000.0, "rationale": "Castle venue"},
                    {"category": "photography", "allocated_amount": 4000.0, "rationale": "High end photographer"},
                    {"category": "florals", "allocated_amount": 3000.0, "rationale": "Wildflower decor"}
                ],
                "timeline_items": [
                    {"title": "Book Venue", "description": "Choose and lock in castle venue", "months_before": 12.0, "kind": "planning"},
                    {"title": "HSE Notification", "description": "Register for HSE appointment", "months_before": 3.0, "kind": "planning"}
                ],
                "rationale_summary": "Realistic budget, seeding lines.",
                "confidence_score": 0.95
            }
            
            planner_prompts = []

            async def mock_generate_content_success(*args, **kwargs):
                planner_prompts.append(kwargs.get("contents"))
                return MockResponse(json.dumps(planner_response))
                
            mock_models.generate_content = mock_generate_content_success
            
            # An old euro row from before B42 must survive a planner run untouched.
            db.add(BudgetLine(id="bl_pre_b42", wedding_id="wedding_intake_test",
                              category="venue", allocated_amount=12000.0))
            await db.commit()

            # Run the planner agent
            res_planner = await approved(run_intake_planner, db, "wedding_intake_test")
            
            print(f"   * Status returned: {res_planner.get('status') or 'success'}")
            assert res_planner.get("is_budget_realistic") is True
            # The couple's names never reach the model (PD-009, rule 3).
            assert len(planner_prompts) == 1
            assert "Clara" not in planner_prompts[0] and "couple_name" not in planner_prompts[0]
            
            # Verify records were inserted
            bl_result = await db.exec(select(BudgetLine).where(BudgetLine.wedding_id == "wedding_intake_test"))
            budget_lines = bl_result.all()
            # B42: the planner no longer writes old euro BudgetLine rows; its draft split
            # stays in the decision log, and the couple's budget is the PD-004 tables.
            print(f"   * Old budget lines after the run: {len(budget_lines)} (expected 1, B42)")
            assert [bl.id for bl in budget_lines] == ["bl_pre_b42"]
            assert budget_lines[0].allocated_amount == 12000.0
            
            # PD-007: the planning checklist replaced the generated timeline, so the planner
            # writes no timeline items or checklist tasks, even when the model returns some.
            tl_result = await db.exec(select(TimelineItem).where(TimelineItem.wedding_id == "wedding_intake_test"))
            timeline_items = tl_result.all()
            print(f"   * Timeline items created: {len(timeline_items)} (expected 0, PD-007)")
            assert len(timeline_items) == 0
            ct_result = await db.exec(select(ChecklistTask).where(ChecklistTask.wedding_id == "wedding_intake_test"))
            assert ct_result.all() == []
            
            # Verify pending/success audit log entry
            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_intake_test", AgentDecisionLog.agent_id == "intake_planner")
            )
            logs = log_result.all()
            print(f"   * Intake planner audit logs: {len(logs)}")
            assert len(logs) == 1
            assert logs[0].status == "success"
            assert logs[0].decision_type == "intake_plan"
            assert len(logs[0].output_payload.get("budget_lines", [])) == 3

            # Success moves the wedding straight to planning; there's no paid preview (PD-003).
            w_after = (await db.exec(select(Wedding).where(Wedding.id == "wedding_intake_test"))).first()
            await db.refresh(w_after)
            assert w_after.status == "planning", w_after.status
            print("   * Wedding status after a successful plan: planning")
            
            
            # --- TEST 2: INTAKE PLANNER GUARDRAIL BLOCK (UNREALISTIC BUDGET) ---
            print("\nTEST 2: Running Intake Planner (Budget Guardrail Path)...")
            # Clear previous entries to make a fresh unrealistic intake test
            wedding_result = await db.exec(select(Wedding).where(Wedding.id == "wedding_intake_test"))
            wedding_intake = wedding_result.first()
            wedding_intake.status = "intake"
            db.add(wedding_intake)
            
            # Delete previous budget lines and timeline items
            for bl in budget_lines:
                await db.delete(bl)
            for tl in timeline_items:
                await db.delete(tl)
            await db.commit()
            
            planner_blocked_response = {
                "is_budget_realistic": False,
                "guardrail_warning": "Catering and venue for 100 guests in Sligo requires at least €12,000.",
                "budget_lines": [],
                "timeline_items": [],
                "rationale_summary": "Unrealistic budget.",
                "confidence_score": 0.9
            }
            
            async def mock_generate_content_blocked(*args, **kwargs):
                return MockResponse(json.dumps(planner_blocked_response))
                
            mock_models.generate_content = mock_generate_content_blocked
            
            res_planner_blocked = await approved(run_intake_planner, db, "wedding_intake_test")
            print(f"   * Status returned: {res_planner_blocked.get('status')}")
            assert res_planner_blocked.get("status") == "blocked"
            assert "unrealistic" in res_planner_blocked.get("rationale_summary").lower()
            
            # Verify no budget lines or timeline items were inserted
            bl_result = await db.exec(select(BudgetLine).where(BudgetLine.wedding_id == "wedding_intake_test"))
            assert len(bl_result.all()) == 0
            w_blocked = (await db.exec(select(Wedding).where(Wedding.id == "wedding_intake_test"))).first()
            await db.refresh(w_blocked)
            assert w_blocked.status == "intake", w_blocked.status
            
            # Verify audit log reflects guardrail block
            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_intake_test", AgentDecisionLog.agent_id == "intake_planner")
                .order_by(AgentDecisionLog.timestamp.desc())
            )
            logs = log_result.all()
            print(f"   * Audit log status: {logs[0].status}, error_kind: {logs[0].error_kind}")
            assert logs[0].status == "blocked_by_guardrail"
            assert logs[0].error_kind == "intake_validation"
            
            
            # --- TEST 3: INTAKE PLANNER GUARDRAIL BLOCK (CATEGORY WHITELIST) ---
            print("\nTEST 3: Running Intake Planner (Category Whitelist Guardrail Path)...")
            planner_whitelist_response = {
                "is_budget_realistic": True,
                "guardrail_warning": "",
                "budget_lines": [
                    {"category": "venue", "allocated_amount": 15000.0, "rationale": "Venue rental"},
                    {"category": "decor", "allocated_amount": 3000.0, "rationale": "Decorations (non-canonical)"}
                ],
                "timeline_items": [],
                "rationale_summary": "Contains non-canonical category.",
                "confidence_score": 0.95
            }
            
            async def mock_generate_content_whitelist(*args, **kwargs):
                return MockResponse(json.dumps(planner_whitelist_response))
                
            mock_models.generate_content = mock_generate_content_whitelist
            
            res_planner_whitelist = await approved(run_intake_planner, db, "wedding_intake_test")
            print(f"   * Status returned: {res_planner_whitelist.get('status')}")
            assert res_planner_whitelist.get("status") == "blocked"
            
            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_intake_test", AgentDecisionLog.agent_id == "intake_planner")
                .order_by(AgentDecisionLog.timestamp.desc())
            )
            logs = log_result.all()
            print(f"   * Audit log status: {logs[0].status}, error_kind: {logs[0].error_kind}")
            assert logs[0].status == "blocked_by_guardrail"
            assert logs[0].error_kind == "category_whitelist"
            
            
            # --- TEST 4: VENUE MATCHER ---
            print("\nTEST 4: Running Venue Matcher...")
            # Restore successful planner run first so budget line is present
            wedding_intake.status = "planning"
            db.add(wedding_intake)
            await db.exec(select(BudgetLine)) # load
            venue_budget_line = BudgetLine(
                id="bl_venue_test",
                wedding_id="wedding_intake_test",
                category="venue",
                allocated_amount=15000.0,
                spent_amount=0.0
            )
            db.add(venue_budget_line)
            await db.commit()
            
            venue_response = {
                "shortlist": [
                    {
                        "vendor_id": "venue_markree_castle",
                        "rank": 1,
                        "matching_rationale": "Fits capacity and Sligo preference.",
                        "draft_inquiry_email": "Dear Markree Castle, we would love a brochure..."
                    }
                ],
                "rationale_summary": "Matched Markree Castle.",
                "confidence_score": 0.92
            }
            
            venue_prompts = []

            async def mock_generate_content_venue(*args, **kwargs):
                venue_prompts.append(kwargs.get("contents"))
                return MockResponse(json.dumps(venue_response))

            mock_models.generate_content = mock_generate_content_venue

            res_matcher = await approved(run_venue_matcher, db, "wedding_intake_test")
            # B44: the budget comes from the couple's own budget, as text with its
            # currency, never the old euro budget line (15000.0 above) or raw cents.
            assert venue_prompts and '"allocated_venue_budget": {' in venue_prompts[-1]
            assert '"currency": "' in venue_prompts[-1] and "amount_cents" not in venue_prompts[-1]
            assert "15000" not in venue_prompts[-1], "the old euro budget line isn't read"
            print(f"   * res_matcher: {res_matcher}")
            print(f"   * Matches found: {len(res_matcher.get('shortlist', []))}")
            assert len(res_matcher.get("shortlist", [])) == 1
            
            # Check booking row created
            b_result = await db.exec(select(Booking).where(Booking.wedding_id == "wedding_intake_test"))
            bookings = b_result.all()
            print(f"   * Booking rows created: {len(bookings)}")
            assert len(bookings) == 1
            assert bookings[0].venue_id == "venue_markree_castle"
            assert bookings[0].status == "shortlisted"
            
            
            # --- TEST 5: VENUE MATCHER HALLUCINATION GUARDRAIL ---
            print("\nTEST 5: Running Venue Matcher (Hallucination Guardrail Path)...")
            venue_hallucinate_response = {
                "shortlist": [
                    {
                        "vendor_id": "venue_hallucinated_invalid_id",
                        "rank": 1,
                        "matching_rationale": "Does not exist in DB.",
                        "draft_inquiry_email": "Hi..."
                    }
                ],
                "rationale_summary": "Made up venue.",
                "confidence_score": 0.8
            }
            
            async def mock_generate_content_hallucinate(*args, **kwargs):
                return MockResponse(json.dumps(venue_hallucinate_response))
                
            mock_models.generate_content = mock_generate_content_hallucinate
            
            res_hallucinate = await approved(run_venue_matcher, db, "wedding_intake_test")
            print(f"   * Status returned: {res_hallucinate.get('status')}")
            assert res_hallucinate.get("status") == "blocked"
            
            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_intake_test", AgentDecisionLog.agent_id == "venue_matcher")
                .order_by(AgentDecisionLog.timestamp.desc())
            )
            logs = log_result.all()
            print(f"   * Audit log status: {logs[0].status}, error_kind: {logs[0].error_kind}")
            assert logs[0].status == "blocked_by_guardrail"
            assert logs[0].error_kind == "hallucination_guardrail"
            
            
            # --- TEST 6: QUOTE EXTRACTOR (UNDER BUDGET) ---
            print("\nTEST 6: Running Quote Extractor (Under Budget Path)...")
            # B44: the alert compares with the couple's own budget category (PD-004), in
            # US dollars. An old euro budget line is still there, and is ignored: a big
            # gap between the two would show which one the alert read.
            from app.db.models import BudgetCategory as _BudgetCategory, BudgetCost as _BudgetCost
            photo_budget = BudgetLine(
                id="bl_photo_test_2",
                wedding_id="wedding_planning_test",
                category="photography",
                allocated_amount=100.0,
                spent_amount=0.0
            )
            db.add(photo_budget)
            db.add(_BudgetCategory(id="cat_photo_test", wedding_id="wedding_planning_test",
                                   name="Photography", planned_cents=400_000))
            await db.commit()

            quote_under_response = {
                "is_available": True,
                "line_items": [
                    {"item": "Full Day Coverage", "description": "8 hours", "amount": 2500.0},
                    {"item": "Album", "description": "Custom leather book", "amount": 500.0}
                ],
                "total_amount": 3000.0,
                "currency": "USD",
                "rationale_text": "Standard package, available.",
                "confidence_score": 0.95
            }
            
            async def mock_generate_content_quote(*args, **kwargs):
                return MockResponse(json.dumps(quote_under_response))
                
            mock_models.generate_content = mock_generate_content_quote
            
            res_extractor = await approved(run_quote_extractor, 
                db, 
                "wedding_planning_test", 
                "booking_photo_test", 
                "Hi Clara, I am available! My standard package with album is €3,000 total."
            )
            
            # Check booking transitioned to quoted
            booking_result = await db.exec(select(Booking).where(Booking.id == "booking_photo_test"))
            booking = booking_result.first()
            print(f"   * Booking status updated: {booking.status}")
            assert booking.status == "quoted"
            
            # Check quote row created
            q_result = await db.exec(select(Quote).where(Quote.booking_id == "booking_photo_test"))
            quotes = q_result.all()
            print(f"   * Quote rows created: {len(quotes)}")
            assert len(quotes) == 1
            assert quotes[0].total_amount == 3000.0
            
            # Verify no budget alert log is created
            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_planning_test", AgentDecisionLog.agent_id == "budget_monitor")
            )
            assert len(log_result.all()) == 0
            
            
            # --- TEST 7: QUOTE EXTRACTOR (OVER BUDGET ALERT TRIGGER) ---
            print("\nTEST 7: Running Quote Extractor (Over Budget Path)...")
            # Update photo booking status back to inquired
            booking.status = "inquired"
            db.add(booking)
            await db.commit()
            
            quote_over_response = {
                "is_available": True,
                "line_items": [
                    {"item": "Luxury Package", "description": "All-in coverage + engagement", "amount": 5000.0}
                ],
                "total_amount": 5000.0,
                "currency": "USD",
                "rationale_text": "Premium package exceeds photo budget of $4,000.",
                "confidence_score": 0.95
            }

            async def mock_generate_content_quote_over(*args, **kwargs):
                return MockResponse(json.dumps(quote_over_response))

            mock_models.generate_content = mock_generate_content_quote_over

            res_over = await approved(run_quote_extractor,
                db,
                "wedding_planning_test",
                "booking_photo_test",
                "Hi, luxury package is $5,000."
            )

            # Verify booking transitioned to quoted
            assert booking.status == "quoted"

            # Verify budget_monitor audit log row created automatically as a side effect!
            alert_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_planning_test", AgentDecisionLog.agent_id == "budget_monitor")
            )
            alerts = alert_result.all()
            print(f"   * Budget monitor alerts created: {len(alerts)}")
            assert len(alerts) == 1
            print(f"   * Alert message: {alerts[0].rationale_summary}")
            assert "exceeds" in alerts[0].rationale_summary
            alert = alerts[0].rationale_summary
            assert alert.startswith("Budget alert for Photography: the quote from "), alert
            assert alert.endswith("($5,000) exceeds what you planned ($4,000) by $1,000."), alert
            assert alerts[0].input_payload == {"planned_cents": 400_000, "quote_cents": 500_000}

            # TEST 7a: a quote in another currency isn't compared (no alert rather than a
            # guessed one), and the extractor writes nothing into the couple's budget.
            print("\nTEST 7a: Quote Extractor leaves the budget alone (B44)...")
            booking.status = "inquired"
            db.add(booking)
            await db.commit()
            quote_over_response["currency"] = "EUR"
            await approved(run_quote_extractor, db, "wedding_planning_test",
                           "booking_photo_test", "Hi, luxury package is 5,000 euro.")
            alerts = (await db.exec(select(AgentDecisionLog).where(
                AgentDecisionLog.wedding_id == "wedding_planning_test",
                AgentDecisionLog.agent_id == "budget_monitor"))).all()
            assert len(alerts) == 1, "no alert for a quote in euros against a dollar budget"
            await db.refresh(photo_budget)
            assert photo_budget.spent_amount == 0.0, "the old euro line isn't written either"
            assert (await db.exec(select(_BudgetCost).where(
                _BudgetCost.wedding_id == "wedding_planning_test"))).all() == [], \
                "a quote never becomes an expense; the couple record costs"
            cat = (await db.exec(select(_BudgetCategory).where(
                _BudgetCategory.id == "cat_photo_test"))).first()
            assert cat.planned_cents == 400_000
            print("   * Alerts read the couple's own budget in dollars; nothing is written to it")

            # --- TEST 7b: A REPLY TO ONE OF THE COUPLE'S OWN VENDORS (B62) ---
            print("\nTEST 7b: Reading a reply to the couple's own vendor...")
            from app.agents.extractor import run_vendor_reply_reader, to_cents
            from app.db.models import CoupleVendor, CoupleVendorQuote, BudgetCategory

            assert (to_cents(2400), to_cents("19.995"), to_cents(0.1 + 0.2)) == (240000, 2000, 30)
            assert to_cents("nan") is None and to_cents(True) is None and to_cents("x") is None
            own = CoupleVendor(id="cv_test", wedding_id="wedding_planning_test",
                               section="food_drink", name="Fictional Catering",
                               contact_name="Placeholder Person", email="c@example.test",
                               phone="(555) 010-0101", status="contacted")
            db.add(own)
            await db.commit()
            budget_before = [(b.id, b.spent_amount) for b in (await db.exec(
                select(BudgetLine).where(BudgetLine.wedding_id == "wedding_planning_test"))).all()]
            categories_before = len((await db.exec(select(BudgetCategory))).all())

            vendor_prompts = []

            def vendor_reply(payload, usage=True):
                async def _gen(*args, **kwargs):
                    vendor_prompts.append(kwargs)
                    resp = MockResponse(json.dumps(payload), 30, 40)
                    if not usage:
                        resp.usage_metadata = None
                    return resp
                return _gen

            async def vendor_logs():
                return (await db.exec(
                    select(AgentDecisionLog)
                    .where(AgentDecisionLog.wedding_id == "wedding_planning_test",
                           AgentDecisionLog.agent_id == "quote_extractor")
                    .order_by(AgentDecisionLog.timestamp.desc()))).all()

            async def readings():
                return (await db.exec(select(CoupleVendorQuote).where(
                    CoupleVendorQuote.vendor_id == "cv_test"))).all()

            mock_models.generate_content = vendor_reply({
                "is_available": True, "total_amount": 2400.5, "currency": "usd",
                "line_items": [{"item": "Dinner", "amount": 2000}, {"item": "Bar"},
                               {"amount": 5}, "junk"],
                "summary": "Dinner and bar; 20% deposit.", "confidence_score": 0.8})
            pasted = ("Hi, dinner for your group is $2,000 and the bar $400.50. "
                      "Placeholder Person, c@example.test, (555) 010-0101")
            out = await approved(run_vendor_reply_reader, db, "wedding_planning_test",
                                 pasted, vendor_id="cv_test")
            assert out["status"] == "success" and out["total_cents"] == 240050, out
            sent_text = vendor_prompts[-1]["contents"]
            for detail in ("Placeholder", "Person", "c@example.test", "010-0101",
                           "Fictional Catering", "food_drink"):
                assert detail not in sent_text, f"vendor detail sent to the AI: {detail}"
            assert "$2,000" in sent_text, "the reply's prices are sent"
            saved = await readings()
            assert len(saved) == 1
            assert (saved[0].total_cents, saved[0].currency, saved[0].is_available) == \
                (240050, "USD", True)
            assert saved[0].line_items == [{"item": "Dinner", "amount_cents": 200000},
                                           {"item": "Bar", "amount_cents": None}]
            await db.refresh(own)
            assert own.status == "contacted", "the AI never changes the couple's status"
            assert [(b.id, b.spent_amount) for b in (await db.exec(
                select(BudgetLine).where(BudgetLine.wedding_id == "wedding_planning_test"))
            ).all()] == budget_before, "nor the budget"
            assert len((await db.exec(select(BudgetCategory))).all()) == categories_before
            log = (await vendor_logs())[0]
            assert (log.status, log.decision_type, log.confidence_score) == \
                ("success", "quote_draft", 0.8)
            assert (log.tokens_input, log.tokens_output) == (30, 40)
            assert log.input_payload == {"vendor_id": "cv_test"}, \
                "the log holds the vendor's id, not the pasted text"
            stored = json.dumps([log.input_payload, log.output_payload, log.rationale_summary])
            assert "Placeholder" not in stored and "c@example.test" not in stored
            print("   * Success: total in cents, currency as read, status and budget untouched, "
                  "no vendor contact details sent or logged")

            # A role in "Contact person" doesn't block other AI features, and the same
            # words in ordinary text survive; the exact role as written is still removed.
            from app.agents import privacy as _privacy
            from app.agents.planner import SYSTEM_INSTRUCTION as planner_instruction
            role = CoupleVendor(id="cv_role", wedding_id="wedding_planning_test",
                                section="venue", name="Fictional Venue",
                                contact_name="Wedding Coordinator")
            db.add(role)
            await db.commit()
            terms = await _privacy.load_personal_terms(db, "wedding_planning_test")
            assert _privacy.find_personal(planner_instruction,
                                          _privacy._whole_names(terms)) == []
            cleaned = _privacy.redact("Our wedding coordinator packages. Wedding Coordinator",
                                      terms)
            assert cleaned == "Our wedding coordinator packages. [name]", cleaned
            await db.delete(role)
            await db.commit()
            print("   * A role in Contact person blocks nothing; only the whole name is removed")

            # Missing optional fields: no currency or confidence invented; booked-out reply.
            mock_models.generate_content = vendor_reply(
                {"is_available": False, "summary": "Fully booked that day."}, usage=False)
            out = await approved(run_vendor_reply_reader, db, "wedding_planning_test",
                                 "Sorry, we're booked that day.", vendor_id="cv_test")
            assert out["status"] == "success" and out["total_cents"] is None
            newest = sorted(await readings(), key=lambda q: q.created_at)[-1]
            assert (newest.total_cents, newest.currency, newest.is_available) == \
                (None, None, False)
            log = (await vendor_logs())[0]
            assert log.confidence_score is None and log.tokens_input is None, \
                "metrics not reported stay empty"
            await db.refresh(own)
            assert own.status == "contacted"
            print("   * Missing fields: no currency, confidence or tokens invented")

            # A vendor the couple ruled out stays ruled out after the AI reads a reply.
            own.not_selected = True
            db.add(own)
            await db.commit()
            mock_models.generate_content = vendor_reply(
                {"is_available": True, "total_amount": 900, "summary": "Still free."})
            out = await approved(run_vendor_reply_reader, db, "wedding_planning_test",
                                 "We're still free, $900.", vendor_id="cv_test")
            assert out["status"] == "success", out
            await db.refresh(own)
            assert (own.status, own.not_selected) == ("contacted", True), \
                "the AI never changes Not selected either"
            own.not_selected = False
            db.add(own)
            await db.commit()
            print("   * Not selected: an AI reading leaves it as the couple set it")

            # Guardrails: nothing saved when the reading can't be trusted.
            for payload, kind in (
                ({"total_amount": -5, "is_available": True, "summary": "?"}, "implausible_total"),
                ({"total_amount": 5e9, "summary": "?"}, "implausible_total"),
                ({"total_amount": "lots", "summary": "?"}, "implausible_total"),
                ({"summary": "Thanks for reaching out!"}, "nothing_found"),
                ([], "nothing_found"),
            ):
                before = len(await readings())
                mock_models.generate_content = vendor_reply(payload)
                out = await approved(run_vendor_reply_reader, db, "wedding_planning_test",
                                     "Some reply.", vendor_id="cv_test")
                assert (out["status"], out["error_kind"]) == ("blocked", kind), (payload, out)
                assert len(await readings()) == before, "a blocked reading saves nothing"
                log = (await vendor_logs())[0]
                assert (log.status, log.error_kind) == ("blocked_by_guardrail", kind)
            try:
                await approved(run_vendor_reply_reader, db, "wedding_intake_test",
                               "Some reply.", vendor_id="cv_test")
                raise AssertionError("a vendor from another wedding must be refused")
            except ValueError:
                pass
            print("   * Guardrails: odd totals and replies with nothing in them save nothing; "
                  "another wedding's vendor is refused")


            # --- TEST 8: MISSING CONFIDENCE IS LOGGED AS NULL, NOT INVENTED ---
            print("\nTEST 8: Running Venue Matcher (No Confidence Reported)...")
            venue_no_confidence_response = {
                k: v for k, v in venue_response.items() if k != "confidence_score"
            }

            async def mock_generate_content_no_confidence(*args, **kwargs):
                return MockResponse(json.dumps(venue_no_confidence_response))

            mock_models.generate_content = mock_generate_content_no_confidence

            await approved(run_venue_matcher, db, "wedding_intake_test")

            log_result = await db.exec(
                select(AgentDecisionLog)
                .where(AgentDecisionLog.wedding_id == "wedding_intake_test", AgentDecisionLog.agent_id == "venue_matcher")
                .order_by(AgentDecisionLog.timestamp.desc())
            )
            logs = log_result.all()
            print(f"   * Latest status: {logs[0].status}, confidence: {logs[0].confidence_score}")
            assert logs[0].status == "success"
            assert logs[0].confidence_score is None
            reported = [log.confidence_score for log in logs if log.status == "success"]
            assert 0.92 in reported, "a reported confidence must still be logged as-is"

            # --- TEST 9: BUDGET SPLIT (PD-004 call b) ---
            print("\nTEST 9: Running Budget Splitter (Success Path)...")
            from app.agents.budget_split import run_budget_splitter, split_cents
            from app.db.models import BudgetCategory

            async def split_logs():
                return (await db.exec(
                    select(AgentDecisionLog)
                    .where(AgentDecisionLog.wedding_id == "wedding_intake_test",
                           AgentDecisionLog.agent_id == "budget_splitter")
                    .order_by(AgentDecisionLog.timestamp.desc())
                )).all()

            def split_reply(lines, usage=True):
                body = json.dumps({"lines": lines, "rationale_summary": "A first draft."})
                response = MockResponse(body, prompt_tokens=40, output_tokens=60)
                if not usage:
                    response.usage_metadata = None

                async def _gen(*args, **kwargs):
                    return response
                return _gen

            split_kwargs = dict(total_cents=3_333_333, category_names=["Venue", "Chuppah flowers"],
                                guest_count=200, ceremony_type="Jewish")
            mock_models.generate_content = split_reply([
                {"category": "venue", "percent": 50.0, "rationale": "Largest cost."},
                {"category": "Chuppah flowers", "percent": 16.7, "rationale": "Ceremony."},
                {"category": "catering", "percent": 33.3, "rationale": "Per head."},
            ])
            with patch("app.agents.budget_split.get_client", return_value=mock_client):
                out = await approved(run_budget_splitter, db, "wedding_intake_test", **split_kwargs)
            assert out.get("status") != "blocked", out
            amounts = [line["planned_cents"] for line in out["lines"]]
            assert sum(amounts) == 3_333_333, "the split must add up to exactly the total"
            assert all(isinstance(a, int) for a in amounts)
            assert [line["name"] for line in out["lines"]] == ["Venue", "Chuppah flowers", "Catering"]
            assert [line["existing"] for line in out["lines"]] == [True, True, False]
            cats = (await db.exec(select(BudgetCategory).where(
                BudgetCategory.wedding_id == "wedding_intake_test"))).all()
            assert cats == [], "a suggestion must not create or change any category"
            log = (await split_logs())[0]
            assert log.status == "success" and log.decision_type == "budget_split"
            assert log.confidence_score is None, "no confidence is asked for, so none is logged"
            assert (log.tokens_input, log.tokens_output) == (40, 60), "measured tokens are logged"
            assert split_cents(100, [1, 1, 1]) == [34, 33, 33]
            print(f"   * Split of {split_kwargs['total_cents']} cents: {amounts}; nothing saved")

            print("\nTEST 10: Running Budget Splitter (Guardrail Paths)...")
            bad_replies = [
                ("category_whitelist", [{"category": "fireworks", "percent": 100.0}]),
                ("duplicate_category", [{"category": "venue", "percent": 50.0},
                                        {"category": "Venue", "percent": 50.0}]),
                ("duplicate_category", [{"category": "Hair makeup", "percent": 50.0},
                                        {"category": "hair_makeup", "percent": 50.0}]),
                ("invalid_share", [{"category": "venue", "percent": 140.0}]),
                ("shares_dont_add_up", [{"category": "venue", "percent": 60.0},
                                        {"category": "catering", "percent": 20.0}]),
                ("empty_split", []),
            ]
            for kind, lines in bad_replies:
                mock_models.generate_content = split_reply(lines)
                with patch("app.agents.budget_split.get_client", return_value=mock_client):
                    out = await approved(run_budget_splitter, db, "wedding_intake_test", **split_kwargs)
                assert out["status"] == "blocked" and out["error_kind"] == kind, (kind, out)
                log = (await split_logs())[0]
                assert log.status == "blocked_by_guardrail" and log.error_kind == kind
                print(f"   * Blocked: {kind}")
            out = await approved(run_budget_splitter, db, "wedding_intake_test", total_cents=0,
                                            category_names=[])
            assert out["error_kind"] == "no_total"
            print("   * Blocked: no_total (no model call without the couple's total)")

            print("\nTEST 10b: Budget Splitter strips prices from its reasons...")
            priced = ["About $12,000 here.", "Typically 8,000 EUR.", "Allow 5k.",
                      "Around €900 per day.", "Budget 3000 dollars.", "USD 400 each."]
            clean = ["Usually the largest share, around 40%.", "Scales with 150 guests."]
            lines = [{"category": c, "percent": 12.5, "rationale": r}
                     for c, r in zip(["venue", "catering", "florals", "music", "cake",
                                      "transport", "dj", "officiant"], priced + clean)]
            body = json.dumps({"lines": lines, "rationale_summary": "Venue gets $15k."})

            async def _priced(*args, **kwargs):
                return MockResponse(body, prompt_tokens=1, output_tokens=1)
            mock_models.generate_content = _priced
            with patch("app.agents.budget_split.get_client", return_value=mock_client):
                out = await approved(run_budget_splitter, db, "wedding_intake_test", **split_kwargs)
            assert out.get("status") != "blocked", out
            reasons = [line["rationale"] for line in out["lines"]]
            assert reasons == [""] * len(priced) + clean, reasons
            assert out["rationale_summary"] == "", "a priced summary is dropped too"
            assert len(out["warnings"]) == len(priced) + 1
            assert sum(line["planned_cents"] for line in out["lines"]) == 3_333_333
            log = (await split_logs())[0]
            assert "$" not in json.dumps(log.output_payload), "no price reaches the log"
            print("   * Prices in the model's prose are removed; percentages and counts kept")
            assert out["reasons_removed"] == len(priced) + 1, "the screen is told how many"

            print("\nTEST 10c: Budget Splitter strips bare-number prices (B43)...")
            bare = ["Around 12,000 for the venue.", "Allow 1.5 million overall.",
                    "Roughly twelve thousand dollars.", "Plan on 8000 here.",
                    "About 2.5m in total.", "Expect 12.000 for this.",
                    "A few thousand on top.", "Fifty dollars a head.",
                    "Around 12 000 for the venue.", "Allow euro 500 here.",
                    "Fifteen hundred on flowers."]
            clean = ["Usually the largest share, around 40%.", "Scales with 150 guests.",
                     "About 12.5% of the total."]
            names = ["venue", "catering", "florals", "music", "cake", "transport", "dj",
                     "officiant", "photography", "videography", "stationery", "hair_makeup",
                     "other", "Chuppah flowers"]
            share = 100 / len(names)
            lines = [{"category": c, "percent": share, "rationale": r}
                     for c, r in zip(names, bare + clean)]
            body = json.dumps({"lines": lines, "rationale_summary": "A first draft."})

            async def _bare(*args, **kwargs):
                return MockResponse(body, prompt_tokens=1, output_tokens=1)
            mock_models.generate_content = _bare
            with patch("app.agents.budget_split.get_client", return_value=mock_client):
                out = await approved(run_budget_splitter, db, "wedding_intake_test", **split_kwargs)
            assert out.get("status") != "blocked", out
            reasons = [line["rationale"] for line in out["lines"]]
            assert reasons == [""] * len(bare) + clean, reasons
            assert out["rationale_summary"] == "A first draft."
            assert out["reasons_removed"] == len(bare)
            print("   * Bare amounts, thousands and millions removed; percentages and counts kept")

            print("\nTEST 11: Running Budget Splitter (No Usage Reported)...")
            mock_models.generate_content = split_reply(
                [{"category": "venue", "percent": 100.0}], usage=False)
            with patch("app.agents.budget_split.get_client", return_value=mock_client):
                out = await approved(run_budget_splitter, db, "wedding_intake_test", **split_kwargs)
            assert out["lines"][0]["planned_cents"] == 3_333_333
            assert out["lines"][0]["rationale"] == "", "a missing rationale stays empty"
            log = (await split_logs())[0]
            assert (log.tokens_input, log.tokens_output) == (None, None), "missing tokens stay empty"
            assert log.external_api_calls[0]["tokens"] == {"input": None, "output": None}
            print("   * Tokens not reported: logged as empty, not zero")

            print("\nTEST 12: Concierge context reads the checklist (PD-007)...")
            from app.agents.concierge import _build_context
            db.add_all([
                ChecklistTask(wedding_id="wedding_intake_test", stage="2m", position=1,
                              title="Placeholder later task"),
                ChecklistTask(wedding_id="wedding_intake_test", stage="9m", position=1,
                              title="Placeholder sooner task", notes="Private placeholder note"),
                ChecklistTask(wedding_id="wedding_intake_test", stage="9m", position=2,
                              title="Placeholder finished task", done=True),
            ])
            await db.commit()
            w_ctx = (await db.exec(select(Wedding).where(Wedding.id == "wedding_intake_test"))).first()
            context = await _build_context(db, w_ctx)
            assert "Next unfinished checklist tasks:" in context
            assert context.index("Placeholder sooner task") < context.index("Placeholder later task")
            assert "Placeholder finished task" not in context, "done tasks are left out"
            assert "Private placeholder note" not in context, "notes stay out of the prompt"
            print("   * Unfinished tasks in stage order; done tasks and notes left out")
            assert "Clara" not in context, "the couple's names stay out of the prompt (PD-009)"
            assert "Total budget: €30,000" in context
            assert "Budget lines" not in context and "allocated" not in context, \
                "the old euro budget lines aren't read any more (B44)"

            print("\nTEST 12a: Concierge and matchers read the couple's own budget (B44)...")
            import datetime as _dt0
            from app.agents import concierge as concierge_module
            from app.agents.matcher import _category_budget
            from app.db.models import (BudgetCategory as _Cat, BudgetCost as _Cost,
                                       BudgetPayment as _Pay)
            db.add_all([
                _Cat(id="cat_c_venue", wedding_id="wedding_intake_test", name="Venue",
                     planned_cents=1_500_000),
                _Cost(id="cost_c_hall", wedding_id="wedding_intake_test",
                      category_id="cat_c_venue", vendor_name="Placeholder Hall",
                      quoted_cents=1_200_000, notes="Private placeholder budget note",
                      link_url="https://example.test/private-contract",
                      payment_method="Placeholder method"),
                _Cost(id="cost_c_old", wedding_id="wedding_intake_test",
                      category_id="cat_c_venue", vendor_name="Archived Placeholder Barn",
                      quoted_cents=900_000, archived=True),
                _Pay(id="pay_c_1", wedding_id="wedding_intake_test", cost_id="cost_c_hall",
                     kind="deposit", amount_cents=600_000, due_on=_dt0.date(2026, 11, 11),
                     paid=True, reference="Placeholder ref 123"),
                _Pay(id="pay_c_2", wedding_id="wedding_intake_test", cost_id="cost_c_hall",
                     amount_cents=600_000, due_on=_dt0.date(2027, 9, 23)),
                _Pay(id="pay_c_3", wedding_id="wedding_intake_test", cost_id="cost_c_hall",
                     kind="deposit", amount_cents=200_000, due_on=_dt0.date(2027, 9, 23),
                     refundable=True),
                _Pay(id="pay_c_4", wedding_id="wedding_intake_test", cost_id="cost_c_old",
                     amount_cents=1_000, due_on=_dt0.date(2026, 1, 1)),
            ])
            await db.commit()
            real_today = concierge_module.wedding_today
            concierge_module.wedding_today = lambda: _dt0.date(2026, 12, 1)
            try:
                context = await _build_context(db, w_ctx)
            finally:
                concierge_module.wedding_today = real_today
            assert "  - Venue: $15,000 planned / $12,000 committed / $6,000 paid" in context, context
            assert "    - Placeholder Hall: $12,000 (quoted), $6,000 paid, partly paid" in context
            assert "  - Placeholder Hall: $6,000, due 2027-09-23" in context
            assert "  - Placeholder Hall: $2,000, due 2027-09-23, refundable deposit" in context
            assert "Archived Placeholder Barn" not in context, "archived expenses are left out"
            for private in ("Private placeholder budget note", "example.test/private-contract",
                            "Placeholder method", "Placeholder ref 123"):
                assert private not in context, f"{private!r} stays out of the prompt"
            print("   * Concierge: planned, committed, paid and payments due; archived, notes, "
                  "links, methods and references left out")

            # A 20% tip on the hall (PD-017) counts at 20% of its quote, as on the Budget screen.
            db.add(_Cost(id="cost_c_tip", wedding_id="wedding_intake_test",
                         category_id="cat_c_venue", vendor_name="Tip: Placeholder Hall",
                         tip_for_cost_id="cost_c_hall", tip_basis_points=2000))
            await db.commit()
            concierge_module.wedding_today = lambda: _dt0.date(2026, 12, 1)
            try:
                context = await _build_context(db, w_ctx)
            finally:
                concierge_module.wedding_today = real_today
            assert "    - Tip: Placeholder Hall: $2,400 (quoted), $0 paid, unpaid" in context, context
            assert "  - Venue: $15,000 planned / $14,400 committed / $6,000 paid" in context
            await db.delete(await db.get(_Cost, "cost_c_tip"))
            await db.commit()
            print("   * Concierge: a percentage tip counts at its share of the expense's cost")

            w_ctx.budget_total_cents = 5_000_000
            db.add(w_ctx)
            await db.commit()
            assert await _category_budget(db, w_ctx, "venue", 40) == {
                "amount": "$15,000", "currency": "USD",
                "source": "planned for the couple's Venue category"}
            assert await _category_budget(db, w_ctx, "photography", 10) == {
                "amount": "$5,000", "currency": "USD",
                "source": "a rough 10% share of the couple's total budget"}
            venue_cat = await db.get(_Cat, "cat_c_venue")
            venue_cat.name = "Venue & Catering"
            db.add(venue_cat)
            await db.commit()
            assert (await _category_budget(db, w_ctx, "venue", 40))["amount"] == "$15,000", \
                "the venue matcher reads the Venue & Catering category 0009 may create"
            w_ctx.budget_total_cents = None
            db.add(w_ctx)
            await db.commit()
            assert await _category_budget(db, w_ctx, "photography", 10) == {
                "amount": "3,000.00 EUR", "currency": "EUR",
                "source": "a rough 10% share of an older setup-form estimate"}, \
                "an older euro estimate is still used, labelled in its own currency"
            saved_total = w_ctx.budget_total
            w_ctx.budget_total = None
            db.add(w_ctx)
            await db.commit()
            assert (await _category_budget(db, w_ctx, "photography", 10))["amount"] is None, \
                "no budget is sent as null, never 0"
            w_ctx.budget_total = saved_total
            db.add(w_ctx)
            await db.commit()
            for row_id, model in (("pay_c_1", _Pay), ("pay_c_2", _Pay), ("pay_c_3", _Pay),
                                  ("pay_c_4", _Pay), ("cost_c_hall", _Cost),
                                  ("cost_c_old", _Cost), ("cat_c_venue", _Cat)):
                await db.delete(await db.get(model, row_id))
            await db.commit()
            print("   * Matchers: the couple's category plan, else a share of their total, "
                  "else null")

            # B48: due dates read "provisional" until the couple confirm the date.
            import datetime as _dt
            w_ctx.wedding_date = _dt.date(2027, 10, 23)
            db.add(w_ctx)
            await db.commit()
            context = await _build_context(db, w_ctx)
            assert w_ctx.wedding_date_confirmed is False, "new weddings start unconfirmed"
            assert "date 2027-10-23 (provisional)." in context, context
            assert "Placeholder sooner task (9 Months Before, due " in context
            assert context.count("(provisional)") == 3, context
            w_ctx.wedding_date_confirmed = True
            db.add(w_ctx)
            await db.commit()
            context = await _build_context(db, w_ctx)
            assert "provisional" not in context, context
            assert "date 2027-10-23." in context and ", due 2027-01-23)" in context, context
            w_ctx.wedding_date, w_ctx.wedding_date_confirmed = None, False
            db.add(w_ctx)
            await db.commit()
            print("   * Due dates say 'provisional' until the couple confirm the date (B48)")

            print("\nTEST 12b: A setup-form wedding: blank budget, US dollars (PD-009)...")
            model_calls = []

            async def must_not_call(*args, **kwargs):
                model_calls.append(kwargs)
                raise AssertionError("the planner must not call the model here")

            mock_models.generate_content = must_not_call
            db.add(Wedding(
                id="wedding_setup_test", couple_user_id="couple_1", status="intake",
                budget_total=None, currency="USD", region="Placeholder City, ST, Country",
                ceremony_type="Jewish", guest_count_estimate=225,
            ))
            await db.commit()

            async def setup_logs():
                return (await db.exec(
                    select(AgentDecisionLog)
                    .where(AgentDecisionLog.wedding_id == "wedding_setup_test",
                           AgentDecisionLog.agent_id == "intake_planner")
                    .order_by(AgentDecisionLog.timestamp.desc())
                )).all()

            out = await approved(run_intake_planner, db, "wedding_setup_test")
            assert out["budget_check"] == "skipped" and out["skip_reason"] == "no_budget", out
            assert "budget_lines" not in out, "no split is drafted without a budget"
            w_setup = (await db.exec(select(Wedding).where(Wedding.id == "wedding_setup_test"))).first()
            await db.refresh(w_setup)
            assert w_setup.status == "planning", "a blank budget never leaves setup stuck"
            log = (await setup_logs())[0]
            assert log.status == "success"
            assert log.model_id is None and log.confidence_score is None, "no call, no metrics"
            assert log.prompt_version is None, "no prompt was sent"
            assert (log.tokens_input, log.tokens_output) == (None, None)
            assert log.external_api_calls == []
            print("   * Blank budget: no model call, wedding moves to planning, no invented metrics")

            # A dollar budget isn't judged against the Irish euro price guide (B11).
            w_setup.budget_total = 40000.0
            w_setup.status = "intake"
            db.add(w_setup)
            await db.commit()
            out = await approved(run_intake_planner, db, "wedding_setup_test")
            assert out["skip_reason"] == "not_irish_pricing", out
            await db.refresh(w_setup)
            assert w_setup.status == "planning"
            assert model_calls == [], "the model was never called for this wedding"
            print("   * Dollar budget: Irish price check skipped, no Irish-priced split")

            w_setup.budget_total = None
            db.add(w_setup)
            await db.commit()
            context = await _build_context(db, w_setup)
            assert "Total budget: not set yet." in context and "€" not in context, context
            print("   * Concierge context: a blank budget reads 'not set yet', not 0")

            # The couple's own dollar total wins over an older intake figure, in dollars.
            w_setup.budget_total = 40000.0
            w_setup.budget_total_cents = 5_000_050
            db.add(w_setup)
            await db.commit()
            context = await _build_context(db, w_setup)
            assert "Total budget: $50,000.50 (US dollars)." in context and "€" not in context, context
            print("   * Concierge context: the couple's dollar total, never shown in euros")

    # PD-008 (B49): no guest or party name, contact detail or dietary note reaches
    # Gemini or the decision log, from any agent. All data here is fictional.
    print("\nTEST 12c: Guest and party personal data never reaches a prompt (PD-008)...")
    from types import SimpleNamespace
    from app.db.models import Guest
    from app.agents.concierge import run_concierge
    from app.agents.budget_split import run_budget_splitter
    from app.agents import privacy

    forbidden = [
        "ottoline", "quarrington", "ottoline.q@example.test", "555 0142", "5550142",
        "barnaby", "fennimore", "201-3344", "2013344", "peanut allergy", "epipen",
        "priya", "david", "priya.david@example.com", "holt", "3125550199",
        "type-1 diabetic", "wilhelmina", "thackeray", "siobh", "bhriain",
        "\\u00e1",
    ]

    def leaks(text) -> list:
        lowered = (text or "").lower()
        return [term for term in forbidden if term in lowered]

    sent = []

    async def capture(*args, **kwargs):
        sent.append(kwargs)
        contents = kwargs.get("contents") or ""
        if "COUPLE'S QUESTION" in contents:
            return MockResponse(json.dumps({"reply": "Yes, that works.", "confidence_score": 0.8}))
        if "Suggest a starting split" in contents:
            return MockResponse(json.dumps({"lines": [
                {"category": "Venue", "percent": 90, "rationale": "Main cost."},
                {"category": "[name]'s travel", "percent": 10, "rationale": "Travel."}],
                "rationale_summary": "One line."}))
        if "Create a wedding plan" in contents:
            return MockResponse(json.dumps({
                "is_budget_realistic": True, "guardrail_warning": "", "budget_lines": [],
                "rationale_summary": "Fine.", "confidence_score": 0.9}))
        if "Match " in contents:
            return MockResponse(json.dumps({
                "shortlist": [], "rationale_summary": "None.", "confidence_score": 0.5}))
        return MockResponse(json.dumps({
            "is_available": True, "line_items": [], "total_amount": 3200.0,
            "currency": "EUR", "rationale_text": "Per-head menu.", "confidence_score": 0.9}))

    priv_client = MagicMock()
    priv_client.aio.models.generate_content = capture
    wid = "wedding_planning_test"
    with patch("app.agents.planner.get_client", return_value=priv_client), \
         patch("app.agents.matcher.get_client", return_value=priv_client), \
         patch("app.agents.extractor.get_client", return_value=priv_client), \
         patch("app.agents.concierge.get_client", return_value=priv_client), \
         patch("app.agents.budget_split.get_client", return_value=priv_client):
        async with async_session_maker() as db:
            db.add_all([
                Guest(wedding_id=wid, name="Ottoline Quarrington",
                      email="ottoline.q@example.test", phone="+353 87 555 0142",
                      dietary="Severe peanut allergy, carries an EpiPen"),
                Guest(wedding_id=wid, name="Barnaby Fennimore-Holt",
                      phone="(555) 201-3344", dietary="vegetarian"),
                Guest(wedding_id=wid, name="Siobhán Ní Bhriain"),
                Guest(wedding_id=wid, name="Wilhelmina Thackeray",
                      phone="3125550199", dietary="Type-1 diabetic"),
                ChecklistTask(wedding_id=wid, stage="9m", position=1,
                              title="Ask Ottoline Quarrington about the cake"),
            ])
            w_priv = (await db.exec(select(Wedding).where(Wedding.id == wid))).first()
            w_priv.style_notes = "Rustic, with Barnaby playing harp; ask Priya and Siobhán."
            db.add(w_priv)
            await db.commit()
            logs_before = {log.id for log in (await db.exec(select(AgentDecisionLog))).all()}

            question = (
                "Can Ottoline Quarrington (ottoline.q@example.test, 087 555 0142) sit near "
                "Barnaby? She has a severe peanut allergy, carries an EpiPen. "
                "We have 12 vegetarian guests and a budget of €3,200 for 2027-06-12. Priya. "
                "Also can ottoline and FENNIMORE and holt sit together? Call 3125550199. "
                "One guest is type 1, diabetic. Siobhan says hi."
            )
            await approved(run_concierge, db, wid, message=question)
            concierge_prompt = sent[-1]["contents"]
            assert "12 vegetarian guests" in concierge_prompt, "counts and categories may be sent"
            assert "€3,200" in concierge_prompt and "2027-06-12" in concierge_prompt
            assert "[name]" in concierge_prompt and "[dietary note]" in concierge_prompt

            await approved(run_quote_extractor, 
                db, wid, "booking_photo_test",
                "Dear Priya and David,\nBarnaby Fennimore-Holt's vegetarian menu is fine. "
                "Ottoline QUARRINGTON can reach me on +1 (555) 201-3344 or "
                "ottoline.q@example.test. 12 vegetarian mains at €40 each; total €3,200.",
            )
            extractor_prompt = sent[-1]["contents"]
            assert "12 vegetarian mains at €40 each; total €3,200." in extractor_prompt

            await approved(run_intake_planner, db, wid, force=True)
            await approved(run_venue_matcher, db, wid)
            await approved(run_supplier_matcher, db, wid, "photography")
            split = await approved(run_budget_splitter, db, wid, total_cents=1_000_000,
                                      category_names=["Venue", "Siobhán's travel"])

            assert split.get("status") != "blocked", split
            assert [line["name"] for line in split["lines"]] == ["Venue", "Siobhán's travel"], \
                "a category named after a guest is sent without the name, then mapped back"
            assert len(sent) == 6, f"every agent called the model once ({len(sent)})"
            for call in sent:
                instruction = getattr(call.get("config"), "system_instruction", "") or ""
                assert not leaks(call.get("contents")), leaks(call.get("contents"))
                assert not leaks(instruction), leaks(instruction)
            print("   * Concierge, quote extractor, planner, both matchers and the budget "
                  "splitter: no names, contacts or dietary notes sent; counts kept")

            new_logs = [log for log in (await db.exec(select(AgentDecisionLog))).all()
                        if log.id not in logs_before]
            assert len(new_logs) == 6, len(new_logs)
            for log in new_logs:
                stored = json.dumps([log.input_payload, log.output_payload,
                                     log.rationale_summary, log.error_message],
                                    ensure_ascii=False)
                assert not leaks(stored), (log.agent_id, leaks(stored))
            print("   * Decision log rows hold no guest or party personal data")

            # Refuses, rather than sends, if a detail is still there after redaction.
            calls_before = len(sent)
            try:
                await privacy.send_prompt(
                    db, wid, priv_client, model="m", contents="Seat plan",
                    config=SimpleNamespace(system_instruction="Greet Ottoline Quarrington."))
                raise AssertionError("a prompt holding a guest name must not be sent")
            except privacy.PersonalDataInPrompt:
                pass
            assert len(sent) == calls_before, "nothing was sent"
            print("   * A prompt that still holds a guest detail is refused, not sent")

            # PD-008 follow-up 2: nothing is sent until the person has seen the cleaned
            # text and clicked to send, and what's sent is exactly what they saw.
            print("\nTEST 12d: Nothing reaches Gemini without the person's click (PD-008)...")
            from app.agents.privacy import PromptNotApproved

            def logs_now():
                return db.exec(select(AgentDecisionLog))

            runs = [
                ("concierge", run_concierge, (), {"message": "Can Ottoline sit with 12 vegetarians?"}),
                ("quote_extractor", run_quote_extractor,
                 ("booking_photo_test", "Dear Priya, total €3,200 for 12 vegetarian mains."), {}),
                ("quote_extractor", run_vendor_reply_reader,
                 ("Dear Priya, total €3,200 for 12 vegetarian mains.",), {"vendor_id": "cv_test"}),
                ("intake_planner", run_intake_planner, (), {"force": True}),
                ("venue_matcher", run_venue_matcher, (), {}),
                ("supplier_matcher", run_supplier_matcher, ("photography",), {}),
                ("budget_splitter", run_budget_splitter, (),
                 {"total_cents": 1_000_000, "category_names": ["Venue", "Siobhán's travel"]}),
            ]
            for name, agent, args, kwargs in runs:
                rows_before = len((await logs_now()).all())
                calls_before = len(sent)

                check = await agent(db, wid, *args, preview_only=True, **kwargs)
                assert check["needs_review"] is True and check["preview"], (name, check)
                preview = check["preview"]
                assert not leaks(preview), (name, leaks(preview))
                assert "[name]" in preview, f"{name}: known names are removed before the preview"
                assert len(sent) == calls_before, f"{name}: a preview sends nothing"
                assert len((await logs_now()).all()) == rows_before, \
                    f"{name}: a preview writes no decision row, since nothing was decided"

                # No click, or a click on any other text: refused and logged, not sent.
                for other in (None, preview + " Ottoline", preview.replace("[name]", "Priya", 1),
                              preview[:-1]):
                    approval = {} if other is None else {"approved_prompt": other}
                    try:
                        await agent(db, wid, *args, **approval, **kwargs)
                        raise AssertionError(f"{name}: sent without approval of this text")
                    except PromptNotApproved:
                        pass
                    assert len(sent) == calls_before, f"{name}: nothing was sent"
                refused = (await db.exec(
                    select(AgentDecisionLog).where(AgentDecisionLog.agent_id == name)
                    .order_by(AgentDecisionLog.timestamp.desc()))).first()
                assert (refused.status, refused.error_kind) == ("error", "PromptNotApproved"), \
                    (name, refused.status, refused.error_kind)

                # The click on the previewed text sends exactly that text, once.
                await agent(db, wid, *args, approved_prompt=preview, **kwargs)
                assert len(sent) == calls_before + 1, f"{name}: the approved text was sent once"
                assert sent[-1]["contents"] == preview, f"{name}: sent text equals previewed text"
            print("   * Every agent, and the own-vendor reply reader: no call without the "
                  "click, none for other text; "
                  "the sent text is the previewed text")

            # A first name that's also a word in the app's own instructions ("Mark
            # is_available", "Irish") doesn't block the AI; the guest's name is still
            # removed from what's sent.
            guest_mark = Guest(wedding_id=wid, name="Mark Irish-Return")
            db.add(guest_mark)
            await db.commit()
            for name, agent, args, kwargs in runs:
                calls_before = len(sent)
                await approved(agent, db, wid, *args, **kwargs)
                assert len(sent) == calls_before + 1, f"{name}: refused over a name part"
                assert "Irish-Return" not in sent[-1]["contents"], name
            await db.delete(guest_mark)
            await db.commit()
            print("   * A guest called Mark (a word in the instructions) doesn't block the AI")

            # A preview changes nothing, even on a path that would (the planner's skip).
            w_skip = (await db.exec(select(Wedding).where(Wedding.id == "wedding_setup_test"))).first()
            w_skip.status = "intake"
            db.add(w_skip)
            await db.commit()
            calls_before = len(sent)
            check = await run_intake_planner(db, "wedding_setup_test", preview_only=True)
            assert check == {"needs_review": False}, check
            await db.refresh(w_skip)
            assert w_skip.status == "intake", "a preview keeps no change"
            assert len(sent) == calls_before
            print("   * A run with no AI call needs no check, and its preview changes nothing")

            # Only send_prompt reaches the client, and it won't send outside an agent run.
            try:
                await privacy.send_prompt(db, wid, priv_client, model="m", contents="Seat plan",
                                          config=SimpleNamespace(system_instruction=""))
                raise AssertionError("send_prompt must not send without an approved text")
            except PromptNotApproved:
                pass
            assert len(sent) == calls_before
            print("   * Outside an approved agent run, nothing is sent")

    # Every model call goes through the guardrail: nothing else uses the Gemini client.
    app_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "app")
    allowed_files = {os.path.join("agents", "privacy.py"), os.path.join("agents", "base.py")}
    client_use = re.compile(r"generate_content|\.models\.|\.chats\b|\.files\b|\.live\b"
                            r"|count_tokens|genai\.Client")
    direct = []
    for root, _dirs, files in os.walk(app_dir):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, app_dir)
            if name.endswith(".py") and rel not in allowed_files:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                if client_use.search(source) or ("get_client(" in source
                                                 and "send_prompt(" not in source):
                    direct.append(rel)
    assert direct == [], f"call Gemini only through privacy.send_prompt: {direct}"
    print("   * Only privacy.send_prompt calls the model")

    # The production path must reach the same decorated agent, not an HTTP stub.
    print("\nTEST 13: Direct production dispatch uses the decorated agent...")
    from app.utils.direct_tasks import execute_agent_task
    from unittest.mock import AsyncMock
    from app.config import settings
    from app.utils.tasks import enqueue_agent_task
    with patch("app.utils.direct_tasks.run_intake_planner", new_callable=AsyncMock) as run:
        run.return_value = {"status": "success"}
        out = await execute_agent_task(
            "intake-planner", {"wedding_id": "wedding_intake_test", "force": True}
        )
        assert out["status"] == "success"
        assert run.await_args.args[1] == "wedding_intake_test"
        assert run.await_args.kwargs == {"force": True, "trigger": "couple_action"}
    # Failure must retain the orchestrator's error row when invoked by dispatch.
    previous = settings.DIRECT_AGENT_EXECUTION
    settings.DIRECT_AGENT_EXECUTION = True
    try:
        from fastapi import HTTPException
        with patch("app.agents.planner.get_client", side_effect=RuntimeError("test unavailable")):
            try:
                await enqueue_agent_task(
                    "intake-planner", {"wedding_id": "wedding_intake_test", "force": True}
                )
                raise AssertionError("Expected an explicit AI failure")
            except HTTPException as exc:
                assert exc.status_code == 502
        async with async_session_maker() as db:
            rows = (await db.exec(select(AgentDecisionLog).where(
                AgentDecisionLog.wedding_id == "wedding_intake_test",
                AgentDecisionLog.agent_id == "intake_planner",
                AgentDecisionLog.status == "error",
            ))).all()
            assert rows, "Direct execution must preserve a recorded agent failure"
    finally:
        settings.DIRECT_AGENT_EXECUTION = previous
    print("   * Real dispatch reaches the agent; provider failures are logged and returned")
    print("\n--- ASYNC AGENT Logic VERIFICATION SUCCESS ---")

def main():
    try:
        asyncio.run(run_async_verification())
    finally:
        # Clean up test SQLite file
        if os.path.exists("./verify_agents_test.db"):
            os.remove("./verify_agents_test.db")
            print("   Temporary database file cleaned up.")

if __name__ == "__main__":
    main()
