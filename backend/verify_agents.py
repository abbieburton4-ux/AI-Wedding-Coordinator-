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
from app.agents.extractor import run_quote_extractor

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
            
            async def mock_generate_content_venue(*args, **kwargs):
                return MockResponse(json.dumps(venue_response))
                
            mock_models.generate_content = mock_generate_content_venue
            
            res_matcher = await approved(run_venue_matcher, db, "wedding_intake_test")
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
            # Create pre-made budget line for photography
            photo_budget = BudgetLine(
                id="bl_photo_test_2",
                wedding_id="wedding_planning_test",
                category="photography",
                allocated_amount=4000.0,
                spent_amount=0.0
            )
            db.add(photo_budget)
            await db.commit()
            
            quote_under_response = {
                "is_available": True,
                "line_items": [
                    {"item": "Full Day Coverage", "description": "8 hours", "amount": 2500.0},
                    {"item": "Album", "description": "Custom leather book", "amount": 500.0}
                ],
                "total_amount": 3000.0,
                "currency": "EUR",
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
                "currency": "EUR",
                "rationale_text": "Premium package exceeds photo budget of €4,000.",
                "confidence_score": 0.95
            }
            
            async def mock_generate_content_quote_over(*args, **kwargs):
                return MockResponse(json.dumps(quote_over_response))
                
            mock_models.generate_content = mock_generate_content_quote_over
            
            res_over = await approved(run_quote_extractor, 
                db,
                "wedding_planning_test",
                "booking_photo_test",
                "Hi, luxury package is €5,000."
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
            print("   * All six agents: no call without the click, none for other text; "
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
