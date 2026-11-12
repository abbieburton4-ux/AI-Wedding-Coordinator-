import os
import sys
from fastapi.testclient import TestClient

# Override environments for local SQLite test session
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./endpoints_test.db"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///./endpoints_test.db"
os.environ["DEVELOPMENT_MODE"] = "True"
os.environ["ALLOW_MOCK_AUTH"] = "True"
# Never copy real deployment access-list addresses into fictional test fixtures.
os.environ["ACCESS_BOOTSTRAP_EMAILS"] = ""

# Inject backend source into paths
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from app.main import app
from app.db.session import sync_engine
from sqlmodel import SQLModel

client = TestClient(app)

def test_api_suite():
    print("--- STARTING API ROUTE VERIFICATION SUITE ---")
    
    # 1. Initialize Tables
    print("1. Re-initializing database schemas...")
    SQLModel.metadata.drop_all(sync_engine)
    SQLModel.metadata.create_all(sync_engine)
    
    # Trigger startup event to run seeding
    with client as c:
        # 2. Uptime/Health check
        print("2. Verifying health and root endpoints...")
        res = c.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"
        
        res = c.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"
        
        # 3. Auth Router (the legacy planner login was removed in PD-003)
        print("3. Verifying dev sign-in and that the legacy business routes are gone...")
        token = "mock-couple_test"
        res = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["role"] == "couple"
        print(f"   * Login Success: dev sign-in as '{token}'")
        assert c.post("/api/v1/auth/planner", json={"email": "x@example.test"}).status_code == 404
        assert c.post("/api/v1/payments/checkout", json={"wedding_id": "x"},
                      headers={"Authorization": f"Bearer {token}"}).status_code == 404
        assert c.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"}).status_code == 404
        assert c.post("/api/v1/webhooks/stripe", json={}).status_code == 404
        assert c.post("/api/v1/webhooks/debug/stripe-mock?wedding_id=x").status_code == 404
        assert c.post("/tasks/plan-cascade", json={"wedding_id": "x"}).status_code == 404
        print("   * Removed: planner login, checkout, metrics and the Stripe webhook (PD-003)")
        
        # 4. Weddings CRUD & Auto-trigger Intake Planner
        print("4. Verifying Wedding creations (P0 Intake Trigger)...")
        headers = {"Authorization": f"Bearer {token}"}
        wedding_payload = {
            "guest_count_estimate": 120,
            "budget_total": 35000.0,
            "region": "Sligo",
            "ceremony_type": "Civil/Humanist",
            "style_notes": "Modern minimalist aesthetic with rustic touches."
        }
        # Creating a wedding queues only the planner, never automatic vendor matching (PD-003, B11).
        from app.api.v1.endpoints import weddings as weddings_module
        queued = []
        real_enqueue = weddings_module.enqueue_agent_task

        async def _record(task, payload):
            queued.append((task, payload))
            return True

        weddings_module.enqueue_agent_task = _record
        try:
            res = c.post("/api/v1/weddings/", json=wedding_payload, headers=headers)
        finally:
            weddings_module.enqueue_agent_task = real_enqueue
        assert res.status_code == 201
        assert queued == [("intake-planner", {"wedding_id": res.json()["id"]})], queued
        wedding = res.json()
        wedding_id = wedding["id"]
        assert wedding["status"] == "intake"
        assert wedding["guest_count_estimate"] == 120
        print(f"   * Creation Success: Wedding {wedding_id} committed in intake status")
        # The older dollars field is only the intake estimate; it doesn't set the total.
        assert wedding["budget_total"] == 35000.0 and wedding["budget_total_cents"] is None
        assert wedding["currency"] == "USD", "the setup form records dollars (PD-009)"

        # The setup form (PD-009): budget left blank, US dollars, Jewish ceremony.
        setup_headers = {"Authorization": "Bearer mock-couple_setup"}
        setup_payload = {
            "guest_count_estimate": 225, "region": "Placeholder City, ST, Country",
            "ceremony_type": "Jewish", "currency": "USD", "wedding_date": "2027-08-21",
            "couple_name": "Fictional Pair",
        }
        for bad in ({"currency": "EUR"}, {"region": "   "}, {"guest_count_estimate": 0},
                    {"budget_total_cents": 0}, {"budget_total": -5.0},
                    {"budget_total_cents": 100, "budget_total": 1.0}):
            res = c.post("/api/v1/weddings/", json=dict(setup_payload, **bad), headers=setup_headers)
            assert res.status_code == 422, (bad, res.status_code, res.text)
        queued.clear()
        weddings_module.enqueue_agent_task = _record
        try:
            res = c.post("/api/v1/weddings/", json=setup_payload, headers=setup_headers)
        finally:
            weddings_module.enqueue_agent_task = real_enqueue
        assert res.status_code == 201, res.text
        setup = res.json()
        assert setup["budget_total"] is None and setup["budget_total_cents"] is None, \
            "a blank budget stays blank, never 0"
        assert (setup["currency"], setup["ceremony_type"], setup["guest_count_estimate"]) == \
            ("USD", "Jewish", 225)
        assert queued == [("intake-planner", {"wedding_id": setup["id"]})], \
            "saving the form never starts vendor matching (PD-003)"
        res = c.patch(f"/api/v1/weddings/{setup['id']}",
                      json={"guest_count_estimate": 230}, headers=setup_headers)
        assert res.status_code == 200 and res.json()["budget_total"] is None
        assert c.patch(f"/api/v1/weddings/{setup['id']}", json={"budget_total": 0},
                       headers=setup_headers).status_code == 422, "0 never stands in for blank"
        res = c.get(f"/api/v1/weddings/{setup['id']}/budget/overview", headers=setup_headers)
        assert res.status_code == 200 and res.json()["totals"]["total_cents"] is None
        # The dashboard's "Adjust my budget" sends the couple's total in cents (B44).
        for bad in ({"budget_total_cents": 0}, {"budget_total_cents": 10.5},
                    {"budget_total_cents": None},
                    {"budget_total_cents": 100, "budget_total": 1.0}):
            assert c.patch(f"/api/v1/weddings/{setup['id']}", json=bad,
                           headers=setup_headers).status_code == 422, bad
        res = c.patch(f"/api/v1/weddings/{setup['id']}", json={"budget_total_cents": 3_000_050},
                      headers=setup_headers)
        assert res.status_code == 200, res.text
        assert (res.json()["budget_total_cents"], res.json()["budget_total"]) == (
            3_000_050, 30000.5), "the couple's total, and the same figure for older readers"
        res = c.get(f"/api/v1/weddings/{setup['id']}/budget/overview", headers=setup_headers)
        assert res.json()["totals"]["total_cents"] == 3_000_050, "the Budget screen shows it"
        # A budget given on the form is the couple's own total, in whole cents.
        res = c.post("/api/v1/weddings/", json=dict(setup_payload, budget_total_cents=4_500_050),
                     headers={"Authorization": "Bearer mock-couple_setup_budget"})
        assert res.status_code == 201, res.text
        assert res.json()["budget_total_cents"] == 4_500_050
        assert res.json()["budget_total"] == 45000.5
        print("   * Setup form: a blank budget saves as blank, in dollars, and only queues the planner")
        
        # Verify access control
        unauth_headers = {"Authorization": "Bearer mock-couple_2"}
        res = c.get(f"/api/v1/weddings/{wedding_id}", headers=unauth_headers)
        assert res.status_code == 403
        print("   * Access Control: Correctly blocked unauthorized couple from reading wedding details")
        
        # 5. Matching endpoints
        print("5. Verifying matching triggers (P0 background tasks enqueuing)...")
        # Each AI action first returns the text it would send and sends nothing; the
        # couple's click repeats it with that text (PD-008 follow-up 2).
        queued.clear()
        weddings_module.enqueue_agent_task = _record
        try:
            res = c.post(f"/api/v1/weddings/{wedding_id}/match", headers=headers)
            assert res.status_code == 202 and res.json()["needs_review"] is True, res.text
            assert "Modern minimalist" in res.json()["preview"] and queued == []
            venue_text = res.json()["preview"]
            res = c.post(f"/api/v1/weddings/{wedding_id}/match", headers=headers,
                         json={"approved_prompt": venue_text + " edited"})
            assert res.json()["needs_review"] is True and res.json()["changed"] is True
            assert queued == [], "a text the couple didn't see is never queued"
            res = c.post(f"/api/v1/weddings/{wedding_id}/suppliers",
                         json={"category": "photography"}, headers=headers)
            assert res.json()["needs_review"] is True and queued == []
            supplier_text = res.json()["preview"]
        finally:
            weddings_module.enqueue_agent_task = real_enqueue
        print("   * Matching: the first call shows the text and queues nothing")

        # Venue Matching
        res = c.post(f"/api/v1/weddings/{wedding_id}/match", headers=headers,
                     json={"approved_prompt": venue_text})
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Venue Matcher enqueued successfully")

        # Supplier Matching
        res = c.post(f"/api/v1/weddings/{wedding_id}/suppliers",
                     json={"category": "photography", "approved_prompt": supplier_text},
                     headers=headers)
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Supplier Matcher (photography) enqueued successfully")
        
        # 6. Inquiries Quote Extractor
        print("6. Verifying raw email parsing quotes trigger...")
        quote_payload = {
            "email_body": "Hi Clara, here is your quote for Castle Dargan. Total price is EUR 4,500.00."
        }
        # booking_photo_test belongs to couple_2's seeded wedding, so couple_2 triggers it.
        res = c.post(
            "/api/v1/inquiries/booking_photo_test/quote", json=quote_payload,
            headers={"Authorization": "Bearer mock-couple_2"},
        )
        assert res.json()["needs_review"] is True, res.text
        assert "Total price is EUR 4,500.00." in res.json()["preview"]
        res = c.post(
            "/api/v1/inquiries/booking_photo_test/quote",
            json=dict(quote_payload, approved_prompt=res.json()["preview"]),
            headers={"Authorization": "Bearer mock-couple_2"},
        )
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Quote Extractor enqueued successfully")
        res = c.post("/api/v1/inquiries/booking_photo_test/quote", json=quote_payload, headers=headers)
        assert res.status_code == 403
        print("   * Access Control: blocked quote extraction on another wedding's booking")

        # A euro budget check uses the AI, so /replan shows the text first and changes
        # nothing until the click; a dollar wedding's check needs no AI, so no review.
        couple_2 = {"Authorization": "Bearer mock-couple_2"}
        queued.clear()
        weddings_module.enqueue_agent_task = _record
        try:
            res = c.post("/api/v1/weddings/wedding_planning_test/replan", headers=couple_2)
            assert res.json()["needs_review"] is True and queued == [], res.text
            assert "Create a wedding plan" in res.json()["preview"]
            res = c.post("/api/v1/weddings/wedding_planning_test/replan", headers=couple_2,
                         json={"approved_prompt": res.json()["preview"]})
            assert res.json()["status"] == "pending", res.text
            assert queued[-1][1]["approved_prompt"], "the approved text goes to the worker"
            queued.clear()
            res = c.post(f"/api/v1/weddings/{wedding_id}/replan", headers=headers)
            assert "needs_review" not in res.json() and len(queued) == 1, res.text
        finally:
            weddings_module.enqueue_agent_task = real_enqueue
        print("   * Replan: the AI budget check waits for the click; a check without AI doesn't")
        
        # 7. Decision Logs & Masked CSV exports
        print("7. Verifying decision logs and PII-redacted CSV exports...")
        res = c.get(f"/api/v1/weddings/{wedding_id}/decisions", headers=headers)
        assert res.status_code == 200
        logs = res.json()
        print(f"   * Logs read: Fetched {len(logs)} decision log traces")
        
        # Export Redacted CSV (the wedding our test couple created)
        res = c.get(f"/api/v1/weddings/{wedding_id}/decisions/export", headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        csv_content = res.text
        # Verify PII masking: no raw emails should leak through
        assert "clara.sean@example.com" not in csv_content
        print(f"   * Export: CSV downloaded ({len(csv_content)} bytes), PII masking verified")
        
        # 7b. Access levels (PD-002)
        print("7b. Verifying access-list levels and sign-in lock-down...")
        from sqlmodel import Session, select as sync_select
        from app.db.models import WeddingMember
        from app.config import settings
        import jwt as pyjwt

        with Session(sync_engine) as s:
            owner_rows = s.exec(sync_select(WeddingMember).where(
                WeddingMember.wedding_id == wedding_id)).all()
        assert [m.level for m in owner_rows] == ["owner"], "creator should be the owner"

        viewer_headers = {"Authorization": "Bearer mock-viewer_1"}
        editor_headers = {"Authorization": "Bearer mock-editor_1"}
        c.get("/api/v1/auth/me", headers=viewer_headers)  # creates the mock users
        c.get("/api/v1/auth/me", headers=editor_headers)
        with Session(sync_engine) as s:
            s.add(WeddingMember(wedding_id=wedding_id, email="viewer_1@example.test",
                                level="viewer", user_id="viewer_1"))
            s.add(WeddingMember(wedding_id=wedding_id, email="editor_1@example.test",
                                level="editor", user_id="editor_1"))
            s.commit()

        assert c.get(f"/api/v1/weddings/{wedding_id}", headers=viewer_headers).status_code == 200
        assert c.get(f"/api/v1/weddings/{wedding_id}/budget", headers=viewer_headers).status_code == 200
        assert wedding_id in [w["id"] for w in c.get("/api/v1/weddings/", headers=viewer_headers).json()]
        assert c.patch(f"/api/v1/weddings/{wedding_id}", json={"guest_count_estimate": 100},
                       headers=viewer_headers).status_code == 403
        assert c.post(f"/api/v1/weddings/{wedding_id}/match", headers=viewer_headers).status_code == 403
        assert c.post(f"/api/v1/weddings/{wedding_id}/concierge", json={"message": "hi"},
                      headers=viewer_headers).status_code == 403
        print("   * Viewer: can read, blocked from edits and agent runs")

        import json as _json
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from app.config import Settings
        from app.db.models import AgentDecisionLog
        concierge_url = f"/api/v1/weddings/{wedding_id}/concierge"
        question = {"message": "Can we afford a harpist?"}
        sent_prompts = []

        async def _reply(**kwargs):
            sent_prompts.append(kwargs["contents"])
            return SimpleNamespace(usage_metadata=None, text=_json.dumps(
                {"reply": "Yes, it fits.", "confidence_score": 0.7}))

        fake_client = MagicMock()
        fake_client.aio.models.generate_content = _reply

        # Aurelia is off by default (PD-010): typed chat and voice both refuse, and
        # nothing goes to Gemini or ElevenLabs, or into the decision log.
        assert Settings.model_fields["ASSISTANT_ENABLED"].default is False
        assert settings.ASSISTANT_ENABLED is False, "Aurelia must be off unless turned on"
        off_detail = "Aurelia, the assistant, is turned off for this wedding."
        with Session(sync_engine) as s:
            log_rows_before = len(s.exec(sync_select(AgentDecisionLog)).all())
        elevenlabs_calls = []

        class _NoElevenLabs:
            def __init__(self, *args, **kwargs):
                elevenlabs_calls.append(args)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, *args, **kwargs):
                elevenlabs_calls.append(args)
                return SimpleNamespace(status_code=200, json=lambda: {"token": "t"},
                                       text="")

        settings.ELEVENLABS_API_KEY = "test-only-not-a-key"
        try:
            with patch("app.agents.concierge.get_client", return_value=fake_client), \
                 patch("app.api.v1.endpoints.voice.httpx.AsyncClient", _NoElevenLabs):
                for body in (question, dict(question, approved_prompt="Can we afford a harpist?")):
                    res = c.post(concierge_url, json=body, headers=editor_headers)
                    assert res.status_code == 403 and res.json()["detail"] == off_detail, res.text
                res = c.post(concierge_url, json=question, headers=headers)
                assert res.status_code == 403 and res.json()["detail"] == off_detail, res.text
                for who in (editor_headers, headers):
                    res = c.get("/api/v1/voice/token", headers=who)
                    assert res.status_code == 403 and res.json()["detail"] == off_detail, res.text
        finally:
            settings.ELEVENLABS_API_KEY = None
        assert sent_prompts == [], "nothing reaches Gemini through the assistant while off"
        assert elevenlabs_calls == [], "nothing reaches ElevenLabs while off"
        with Session(sync_engine) as s:
            assert len(s.exec(sync_select(AgentDecisionLog)).all()) == log_rows_before
        print("   * Aurelia off: chat and voice refuse; nothing sent to Gemini or ElevenLabs")

        # The concierge shows the couple the exact text first, and sends only on their
        # click, only that text (PD-008 follow-up 2). Gemini is mocked. The switch is
        # turned on here so the code stays proven for when Aurelia comes back.
        with patch.object(settings, "ASSISTANT_ENABLED", True), \
             patch("app.agents.concierge.get_client", return_value=fake_client):
            res = c.post(concierge_url, json=question, headers=editor_headers)
            check = res.json()
            assert check["needs_review"] is True and check["changed"] is False, res.text
            assert "Can we afford a harpist?" in check["preview"] and sent_prompts == []
            res = c.post(concierge_url, headers=editor_headers,
                         json=dict(question, approved_prompt=check["preview"] + " Also Ann."))
            assert res.json()["needs_review"] is True and res.json()["changed"] is True
            assert sent_prompts == [], "a text other than the one shown is never sent"
            assert c.post(concierge_url, headers=viewer_headers,
                          json=dict(question, approved_prompt=check["preview"])
                          ).status_code == 403, "a viewer can't send either"
            res = c.post(concierge_url, headers=editor_headers,
                         json=dict(question, approved_prompt=check["preview"]))
            assert res.json() == {"reply": "Yes, it fits."}, res.text
            assert sent_prompts == [check["preview"]], "the text sent is the text shown"
        assert settings.ASSISTANT_ENABLED is False
        print("   * Concierge: shows the text first; the click sends exactly that text")

        # The inbound-email webhook has no one to check the text, so it never sends it.
        # (It can't parse a form here: python-multipart isn't installed, B50.)
        import inspect
        from app.api.v1.endpoints import webhooks as webhooks_module
        webhook_source = inspect.getsource(webhooks_module)
        assert not hasattr(webhooks_module, "enqueue_agent_task")
        assert "quote-extractor" not in webhook_source and "run_quote" not in webhook_source
        assert '"reason": "needs_review"' in webhook_source
        print("   * Inbound email: not sent to the AI unattended")
        assert c.patch(f"/api/v1/weddings/{wedding_id}", json={"guest_count_estimate": 110},
                       headers=editor_headers).status_code == 200
        print("   * Editor: can edit")

        # Managing the access list is owner-only, enforced by the API (PD-002 step 2, B22).
        members_url = f"/api/v1/weddings/{wedding_id}/members"
        assert c.get(f"/api/v1/weddings/{wedding_id}/my-access", headers=viewer_headers).json() == {"level": "viewer"}
        assert c.get(f"/api/v1/weddings/{wedding_id}/my-access", headers=headers).json() == {"level": "owner"}
        assert c.get(f"/api/v1/weddings/{wedding_id}/my-access", headers=unauth_headers).status_code == 403
        for who in (viewer_headers, editor_headers, unauth_headers):
            assert c.get(members_url, headers=who).status_code == 403
            assert c.post(members_url, json={"email": "x@example.test", "level": "viewer"},
                          headers=who).status_code == 403
        assert "manage access" in c.get(members_url, headers=editor_headers).json()["detail"]
        listed = c.get(members_url, headers=headers).json()
        by_email = {m["email"]: m for m in listed}
        assert by_email["viewer_1@example.test"]["level"] == "viewer"
        owner_member = next(m for m in listed if m["level"] == "owner")
        editor_member = by_email["editor_1@example.test"]
        assert c.patch(f"{members_url}/{owner_member['id']}", json={"level": "viewer"},
                       headers=editor_headers).status_code == 403
        assert c.delete(f"{members_url}/{owner_member['id']}", headers=editor_headers).status_code == 403
        assert c.delete(f"{members_url}/{editor_member['id']}", headers=viewer_headers).status_code == 403
        print("   * Access list: viewers, editors and outsiders can't read or change it")

        res = c.post(members_url, json={"email": " Aunt@Example.test ", "level": "viewer"}, headers=headers)
        assert res.status_code == 201 and res.json()["email"] == "aunt@example.test"
        assert res.json()["signed_in"] is False
        aunt_id = res.json()["id"]
        assert c.post(members_url, json={"email": "aunt@example.test", "level": "editor"},
                      headers=headers).status_code == 409
        assert c.post(members_url, json={"email": "not-an-email", "level": "viewer"},
                      headers=headers).status_code == 422
        assert c.post(members_url, json={"email": "x2@example.test", "level": "owner"},
                      headers=headers).status_code == 422
        res = c.post(members_url, json={"email": "uncle@example.test", "level": "viewer"}, headers=headers)
        assert res.status_code == 201  # several people can share a level
        uncle_id = res.json()["id"]
        assert c.patch(f"{members_url}/{aunt_id}", json={"level": "editor"},
                       headers=headers).json()["level"] == "editor"
        assert c.delete(f"{members_url}/{uncle_id}", headers=headers).status_code == 204
        assert c.delete(f"{members_url}/{uncle_id}", headers=headers).status_code == 404
        assert "uncle@example.test" not in [m["email"] for m in c.get(members_url, headers=headers).json()]
        print("   * Access list: an owner can add, change and remove people; nothing is sent")

        # An owner of another wedding (couple_2, seeded) can't reach this wedding's rows.
        assert c.delete(f"/api/v1/weddings/wedding_planning_test/members/{aunt_id}",
                        headers=unauth_headers).status_code == 404
        assert c.patch(f"/api/v1/weddings/wedding_planning_test/members/{aunt_id}",
                       json={"level": "viewer"}, headers=unauth_headers).status_code == 404

        # Owner rows are fixed in the app (PD-002 note, 2026-11-05), including your own.
        for level in ("editor", "viewer"):
            res = c.patch(f"{members_url}/{owner_member['id']}", json={"level": level}, headers=headers)
            assert res.status_code == 409, res.text
            assert "ask the team" in res.json()["detail"]
        res = c.delete(f"{members_url}/{owner_member['id']}", headers=headers)
        assert res.status_code == 409 and "ask the team" in res.json()["detail"], res.text
        assert c.get(members_url, headers=headers).status_code == 200  # still an owner
        # Nobody can be made an owner through the API, by adding or by changing a level.
        assert c.patch(f"{members_url}/{aunt_id}", json={"level": "owner"},
                       headers=headers).status_code == 422
        assert c.patch(f"{members_url}/{editor_member['id']}", json={"level": "owner"},
                       headers=headers).status_code == 422
        with Session(sync_engine) as s:
            s.add(WeddingMember(wedding_id=wedding_id, email="partner@example.test", level="owner"))
            s.commit()
            partner_id = s.exec(sync_select(WeddingMember.id).where(
                WeddingMember.email == "partner@example.test")).one()
        # With both partners listed, neither can demote or remove the other, or themselves.
        assert c.patch(f"{members_url}/{owner_member['id']}", json={"level": "editor"},
                       headers=headers).status_code == 409
        assert c.delete(f"{members_url}/{owner_member['id']}", headers=headers).status_code == 409
        # Look-alike letters (B39): a Kelvin sign, Cyrillic and fullwidth letters.
        for lookalike in ("\u212aate@example.test", "p\u0430rtner@example.test",
                          "\uff50artner@example.test"):
            res = c.post(members_url, json={"email": lookalike, "level": "viewer"}, headers=headers)
            assert res.status_code == 422 and "can't check safely" in res.json()["detail"], res.text
        for level in ("editor", "viewer"):
            res = c.patch(f"{members_url}/{partner_id}", json={"level": level}, headers=headers)
            assert res.status_code == 409 and "ask the team" in res.json()["detail"], res.text
        res = c.delete(f"{members_url}/{partner_id}", headers=headers)
        assert res.status_code == 409 and "ask the team" in res.json()["detail"], res.text
        # The team can still change and remove an owner, on the couple's request.
        import manage_access
        from unittest.mock import patch as mock_patch

        def _team(*argv):
            with mock_patch.object(sys, "argv", ["manage_access.py", *argv, "--wedding", wedding_id]):
                manage_access.main()

        try:
            _team("set", "--email", "p\u0430rtner@example.test", "--level", "viewer")
            raise AssertionError("manage_access accepted a look-alike address")
        except SystemExit as exc:
            assert "can't be matched safely" in str(exc), exc
        _team("set", "--email", " Partner@Example.test ", "--level", "editor")
        with Session(sync_engine) as s:
            assert s.get(WeddingMember, partner_id).level == "editor"
        _team("set", "--email", "partner@example.test", "--level", "owner")
        with Session(sync_engine) as s:
            assert s.get(WeddingMember, partner_id).level == "owner"
        _team("remove", "--email", "partner@example.test")
        with Session(sync_engine) as s:
            assert s.get(WeddingMember, partner_id) is None
        # Everyone else can still be changed and removed.
        assert c.patch(f"{members_url}/{editor_member['id']}", json={"level": "viewer"},
                       headers=headers).json()["level"] == "viewer"
        assert c.patch(f"{members_url}/{editor_member['id']}", json={"level": "editor"},
                       headers=headers).json()["level"] == "editor"
        assert c.delete(f"{members_url}/{aunt_id}", headers=headers).status_code == 204
        print("   * Access list: owners can't be removed, demoted or created through the API")

        # 7c. Budget (PD-004): cents only, viewers read everything but change nothing.
        print("7c. Verifying the budget: categories, vendor costs, payments, contributions...")
        from app.api.v1.endpoints import budget as budget_module
        b_url = f"/api/v1/weddings/{wedding_id}/budget"
        ov = c.get(f"{b_url}/overview", headers=viewer_headers)
        assert ov.status_code == 200, ov.text
        assert ov.json()["totals"]["total_cents"] is None, "no total until the couple set one"
        assert ov.json()["categories"] == [] and ov.json()["next_due"] == []
        assert c.get(f"{b_url}/overview", headers=unauth_headers).status_code == 403

        def clear_category(cat_id):
            # A category with expenses can't be removed (B67), so a test tidying up
            # removes the expenses itself first.
            ov = c.get(f"{b_url}/overview", headers=headers).json()
            for cost in next(k for k in ov["categories"] if k["id"] == cat_id)["costs"]:
                assert c.delete(f"{b_url}/costs/{cost['id']}",
                                headers=headers).status_code == 204
            assert c.delete(f"{b_url}/categories/{cat_id}", headers=headers).status_code == 204

        res = c.post(f"{b_url}/categories", json={"name": "  Venue ", "planned_cents": 1_500_000},
                     headers=headers)
        assert res.status_code == 201 and res.json()["name"] == "Venue", res.text
        venue_cat = res.json()["id"]
        res = c.post(f"{b_url}/categories", json={"name": "Flowers"}, headers=editor_headers)
        assert res.status_code == 201 and res.json()["planned_cents"] is None
        flowers_cat = res.json()["id"]
        assert c.post(f"{b_url}/categories", json={"name": "   "}, headers=headers).status_code == 422
        assert c.post(f"{b_url}/categories", json={"name": "X", "planned_cents": -1},
                      headers=headers).status_code == 422
        assert c.post(f"{b_url}/categories", json={"name": "X", "planned_cents": 10.5},
                      headers=headers).status_code == 422, "amounts are whole cents"
        res = c.patch(f"{b_url}/categories/{flowers_cat}",
                      json={"name": "Florals", "planned_cents": 250_000}, headers=editor_headers)
        assert res.status_code == 200 and res.json()["name"] == "Florals"
        assert c.patch(f"{b_url}/categories/nope", json={"name": "Y"},
                       headers=headers).status_code == 404
        assert c.post(f"{b_url}/categories", json={"name": "venue"},
                      headers=headers).status_code == 409, "no two categories with one name"
        assert c.patch(f"{b_url}/categories/{flowers_cat}", json={"name": " VENUE "},
                       headers=headers).status_code == 409
        assert c.patch(f"{b_url}/categories/{flowers_cat}", json={"name": "florals"},
                       headers=headers).status_code == 200, "renaming to itself is fine"
        assert c.patch(f"{b_url}/categories/{flowers_cat}", json={"name": "Florals"},
                       headers=headers).status_code == 200
        # Two look-alikes can only exist via two adds at the same moment (B43); either
        # one's amount can still be edited, sent with its unchanged name.
        from app.db.models import BudgetCategory as _BudgetCategory
        with Session(sync_engine) as s:
            twin = _BudgetCategory(wedding_id=wedding_id, name="FLORALS")
            s.add(twin)
            s.commit()
            twin_id = twin.id
        for cat_id, cat_name in ((flowers_cat, "Florals"), (twin_id, "FLORALS")):
            res = c.patch(f"{b_url}/categories/{cat_id}",
                          json={"name": cat_name, "planned_cents": 250_000}, headers=headers)
            assert res.status_code == 200, res.text
        assert c.patch(f"{b_url}/categories/{twin_id}", json={"name": " Venue "},
                       headers=headers).status_code == 409, "a real rename is still checked"
        assert c.delete(f"{b_url}/categories/{twin_id}", headers=headers).status_code == 204
        print("   * Categories: add, rename and plan; bad names, duplicates and non-cent "
              "amounts refused")

        res = c.post(f"{b_url}/categories/{venue_cat}/costs",
                     json={"vendor_name": "Sample Hall", "quoted_cents": 1_200_050}, headers=headers)
        assert res.status_code == 201, res.text
        cost_id = res.json()["id"]
        assert c.patch(f"{b_url}/costs/{cost_id}", json={"quoted_cents": 1_200_000},
                       headers=editor_headers).status_code == 200
        res = c.post(f"{b_url}/costs/{cost_id}/payments",
                     json={"kind": "deposit", "amount_cents": 300_000, "due_on": "2020-01-15"},
                     headers=headers)
        assert res.status_code == 201 and res.json()["paid"] is False, res.text
        deposit_id = res.json()["id"]
        res = c.post(f"{b_url}/costs/{cost_id}/payments",
                     json={"amount_cents": 900_000, "due_on": "2099-06-01", "paid": True},
                     headers=headers)
        assert res.status_code == 201 and res.json()["paid"] is False, "new payments start unpaid"
        balance_id = res.json()["id"]
        assert c.post(f"{b_url}/costs/{cost_id}/payments", json={"amount_cents": 0},
                      headers=headers).status_code == 422
        assert c.post(f"{b_url}/costs/{cost_id}/payments", json={"kind": "refund", "amount_cents": 1},
                      headers=headers).status_code == 422
        assert c.patch(f"{b_url}/payments/{balance_id}", json={"paid": True},
                       headers=headers).json()["paid"] is False, "editing can't mark a payment paid"
        print("   * Vendor costs and payments: added unpaid; only the paid click changes that")

        res = c.post(f"{b_url}/contributions",
                     json={"contributor": "Groom's parents", "amount_cents": 500_000,
                           "category_id": venue_cat}, headers=headers)
        assert res.status_code == 201, res.text
        contribution_id = res.json()["id"]
        assert c.post(f"{b_url}/contributions", json={"contributor": "A", "amount_cents": 1,
                      "category_id": "nope"}, headers=headers).status_code == 404
        assert c.patch(f"{b_url}/contributions/{contribution_id}", json={"amount_cents": 600_000},
                       headers=editor_headers).status_code == 200

        # Viewers (family) see it all, contributions included, and can change none of it.
        paid_url = f"{b_url}/payments/{deposit_id}/paid"
        viewer_writes = [
            ("put", f"{b_url}/total", {"total_cents": 1}),
            ("post", f"{b_url}/categories", {"name": "Z"}),
            ("patch", f"{b_url}/categories/{venue_cat}", {"name": "Z"}),
            ("delete", f"{b_url}/categories/{venue_cat}", None),
            ("post", f"{b_url}/categories/{venue_cat}/costs", {"vendor_name": "Z"}),
            ("patch", f"{b_url}/costs/{cost_id}", {"quoted_cents": 1}),
            ("delete", f"{b_url}/costs/{cost_id}", None),
            ("post", f"{b_url}/costs/{cost_id}/payments", {"amount_cents": 1}),
            ("patch", f"{b_url}/payments/{deposit_id}", {"amount_cents": 1}),
            ("put", paid_url, {"paid": True}),
            ("delete", f"{b_url}/payments/{deposit_id}", None),
            ("post", f"{b_url}/contributions", {"contributor": "Z", "amount_cents": 1}),
            ("patch", f"{b_url}/contributions/{contribution_id}", {"amount_cents": 1}),
            ("delete", f"{b_url}/contributions/{contribution_id}", None),
            ("post", f"{b_url}/suggest-split", None),
            ("post", f"{b_url}/apply-split", {"lines": [{"name": "Z", "planned_cents": 1}]}),
            ("put", f"{b_url}/categories/order", {"category_ids": [venue_cat, flowers_cat]}),
            ("post", f"{b_url}/categories/defaults", None),
            ("post", f"{b_url}/categories/defaults/restore", None),
            ("post", f"{b_url}/costs/{cost_id}/duplicate", None),
            ("delete", f"{b_url}/categories/{venue_cat}?move_to={flowers_cat}", None),
        ]
        for method, url, body in viewer_writes:
            kwargs = {"headers": viewer_headers}
            if body is not None:
                kwargs["json"] = body
            res = c.request(method.upper(), url, **kwargs)
            assert res.status_code == 403, (method, url, res.status_code)
            res = c.request(method.upper(), url, **{**kwargs, "headers": unauth_headers})
            assert res.status_code == 403, (method, url, res.status_code)
        print("   * Viewer and outsider: every budget change and the AI split are refused")

        res = c.put(paid_url, json={"paid": True}, headers=editor_headers)
        assert res.status_code == 200 and res.json()["paid"] is True and res.json()["paid_at"]
        first_tick = res.json()
        assert first_tick["paid_by_name"] == "Mock Couple (editor_1)", first_tick
        with Session(sync_engine) as s:
            from app.db.models import BudgetPayment
            assert s.get(BudgetPayment, deposit_id).paid_by_user_id == "editor_1"
        res = c.put(paid_url, json={"paid": True}, headers=headers)
        assert (res.json()["paid_at"], res.json()["paid_by_name"]) == (
            first_tick["paid_at"], first_tick["paid_by_name"]), "a second tick keeps the first"
        with Session(sync_engine) as s:
            assert s.get(BudgetPayment, deposit_id).paid_by_user_id == "editor_1"
        res = c.patch(f"{b_url}/payments/{deposit_id}", json={"due_on": "2020-01-16"},
                      headers=headers)
        assert res.json()["paid_by_name"] == first_tick["paid_by_name"], \
            "editing a paid payment still says who ticked it"
        assert c.patch(f"{b_url}/payments/{deposit_id}", json={"due_on": "2020-01-15"},
                       headers=headers).status_code == 200
        ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
        venue = next(cat for cat in ov["categories"] if cat["id"] == venue_cat)
        assert (venue["planned_cents"], venue["committed_cents"], venue["paid_cents"],
                venue["remaining_cents"]) == (1_500_000, 1_200_000, 300_000, 900_000), venue
        assert ov["totals"] == {"total_cents": None, "planned_cents": 1_750_000,
                                "committed_cents": 1_200_000, "committed_basis": "quote",
                                "paid_cents": 300_000, "remaining_cents": 900_000,
                                "overpaid_cents": 0, "contributions_cents": 600_000,
                                "refundable_cents": 0, "refundable_paid_cents": 0}
        assert [d["payment_id"] for d in ov["next_due"]] == [balance_id]
        assert ov["next_due"][0]["overdue"] is False
        assert ov["contributions"][0]["contributor"] == "Groom's parents"

        # Overpaying one vendor shows as overpaid, never as a negative amount, and doesn't
        # reduce what's still owed elsewhere. "Committed" says where its figure comes from.
        cake_cat = c.post(f"{b_url}/categories", json={"name": "Cake"}, headers=headers).json()["id"]
        bakery = c.post(f"{b_url}/categories/{cake_cat}/costs",
                        json={"vendor_name": "Sample Bakery", "quoted_cents": 10_000},
                        headers=headers).json()["id"]
        over_pay = c.post(f"{b_url}/costs/{bakery}/payments", json={"amount_cents": 15_000},
                          headers=headers).json()["id"]
        c.put(f"{b_url}/payments/{over_pay}/paid", json={"paid": True}, headers=headers)
        toppers = c.post(f"{b_url}/categories/{cake_cat}/costs",
                         json={"vendor_name": "Sample Toppers"}, headers=headers).json()["id"]
        c.post(f"{b_url}/costs/{toppers}/payments", json={"amount_cents": 2_000}, headers=headers)
        ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
        cake = next(cat for cat in ov["categories"] if cat["id"] == cake_cat)
        by_vendor = {cost["vendor_name"]: cost for cost in cake["costs"]}
        assert (by_vendor["Sample Bakery"]["remaining_cents"],
                by_vendor["Sample Bakery"]["overpaid_cents"]) == (0, 5_000)
        assert by_vendor["Sample Bakery"]["committed_basis"] == "quote"
        assert by_vendor["Sample Toppers"]["committed_basis"] == "scheduled"
        assert (cake["committed_basis"], cake["remaining_cents"], cake["overpaid_cents"]) == (
            "mixed", 2_000, 5_000), cake
        assert (ov["totals"]["remaining_cents"], ov["totals"]["overpaid_cents"]) == (
            902_000, 5_000), "an overpayment isn't netted against other vendors"
        assert ov["totals"]["committed_basis"] == "mixed"
        clear_category(cake_cat)
        print("   * Overpaid: shown per vendor, never negative, never netted")

        res = c.put(paid_url, json={"paid": False}, headers=headers)
        assert res.json()["paid"] is False and res.json()["paid_at"] is None
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert ov["next_due"][0]["payment_id"] == deposit_id and ov["next_due"][0]["overdue"] is True
        print("   * Paid: an editor's click marks it, records who; totals and due list follow")

        # The total is optional; the AI split needs it and changes nothing by itself.
        assert c.post(f"{b_url}/suggest-split", headers=headers).status_code == 400
        assert c.put(f"{b_url}/total", json={"total_cents": 0}, headers=headers).status_code == 422
        res = c.put(f"{b_url}/total", json={"total_cents": 4_000_000}, headers=editor_headers)
        assert res.status_code == 200 and res.json()["total_cents"] == 4_000_000
        real_splitter = budget_module.run_budget_splitter
        calls = []

        async def _fake_split(db, wid, **kwargs):
            if kwargs.get("preview_only"):
                return {"needs_review": True, "preview": "Suggest a starting split"}
            calls.append(kwargs)
            return {"suggestion": True, "total_cents": kwargs["total_cents"],
                    "lines": [{"name": "Venue", "planned_cents": 3_000_000, "existing": True,
                               "rationale": "r"},
                              {"name": "Catering", "planned_cents": 1_000_000,
                               "existing": False, "rationale": "r"}],
                    "rationale_summary": "s"}

        async def _blocked_split(db, wid, **kwargs):
            if kwargs.get("preview_only"):
                return {"needs_review": True, "preview": "Suggest a starting split"}
            return {"status": "blocked", "error_kind": "category_whitelist"}

        approve = {"approved_prompt": "Suggest a starting split"}
        budget_module.run_budget_splitter = _fake_split
        try:
            res = c.post(f"{b_url}/suggest-split", headers=headers)
            assert res.json() == {"needs_review": True, "preview": "Suggest a starting split",
                                  "changed": False}, res.text
            assert calls == [], "nothing is asked of the AI before the couple's click"
            res = c.post(f"{b_url}/suggest-split", headers=headers, json=approve)
            assert res.status_code == 200 and len(res.json()["lines"]) == 2, res.text
            assert res.json()["reasons_removed"] == 0, "no reason was removed"
            assert calls[0]["total_cents"] == 4_000_000
            assert calls[0]["approved_prompt"] == approve["approved_prompt"]
            assert sorted(calls[0]["category_names"]) == ["Florals", "Venue"]
            budget_module.run_budget_splitter = _blocked_split
            assert c.post(f"{b_url}/suggest-split", headers=headers,
                          json=approve).status_code == 422
        finally:
            budget_module.run_budget_splitter = real_splitter
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert [cat["planned_cents"] for cat in ov["categories"]] == [1_500_000, 250_000], \
            "a suggestion must change nothing until the couple use it"
        assert c.post(f"{b_url}/apply-split", headers=headers, json={"lines": [
            {"name": "Hair makeup", "planned_cents": 2_000_000},
            {"name": "hair_MAKEUP", "planned_cents": 2_000_000}]}).status_code == 422, \
            "one category can't appear twice in a split"
        assert c.post(f"{b_url}/apply-split", headers=headers, json={"lines": [
            {"name": "venue", "planned_cents": 2_900_000},
            {"name": "Catering", "planned_cents": 1_000_000}]}).status_code == 409, \
            "a split that doesn't add up to the total isn't applied"
        # Two categories differing only by case (possible in data from before the
        # duplicate check): the split refuses rather than updating just one of them.
        with Session(sync_engine) as s:
            from app.db.models import BudgetCategory as BudgetCategoryModel
            twin = BudgetCategoryModel(wedding_id=wedding_id, name="VENUE", planned_cents=7)
            s.add(twin)
            s.commit()
            twin_id = twin.id
        res = c.post(f"{b_url}/apply-split", headers=headers, json={"lines": [
            {"name": "venue", "planned_cents": 2_900_000},
            {"name": "Catering", "planned_cents": 1_100_000}]})
        assert res.status_code == 409 and "VENUE" in res.json()["detail"], res.text
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert [cat["planned_cents"] for cat in ov["categories"]] == [1_500_000, 250_000, 7], \
            "a refused split changes nothing"
        assert c.delete(f"{b_url}/categories/{twin_id}", headers=headers).status_code == 204
        res = c.post(f"{b_url}/apply-split", headers=headers, json={"lines": [
            {"name": "venue", "planned_cents": 2_900_000},
            {"name": "Catering", "planned_cents": 1_100_000}]})
        assert res.status_code == 200, res.text
        planned = {cat["name"]: cat["planned_cents"] for cat in res.json()["categories"]}
        assert planned == {"Venue": 2_900_000, "Florals": 250_000, "Catering": 1_100_000}, planned
        assert sum(planned[n] for n in ("Venue", "Catering")) == 4_000_000, \
            "the applied split adds up to the total"
        assert c.put(f"{b_url}/total", json={"total_cents": None}, headers=headers).json()[
            "total_cents"] is None
        assert c.post(f"{b_url}/apply-split", headers=headers, json={"lines": [
            {"name": "Venue", "planned_cents": 1}]}).status_code == 400, "needs a total"
        print("   * Total: optional; the AI split needs it, saves nothing, and is applied by the couple")

        assert c.delete(f"{b_url}/payments/{balance_id}", headers=headers).status_code == 204
        assert c.delete(f"{b_url}/costs/{cost_id}", headers=editor_headers).status_code == 204
        assert c.delete(f"{b_url}/categories/{venue_cat}", headers=headers).status_code == 204
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert venue_cat not in [cat["id"] for cat in ov["categories"]]
        assert ov["contributions"][0]["category_id"] is None, "contribution stays, untied"
        with Session(sync_engine) as s:
            assert s.get(BudgetPayment, deposit_id) is None, "a removed cost takes its payments"
        assert c.delete(f"{b_url}/contributions/{contribution_id}",
                        headers=headers).status_code == 204
        print("   * Delete: payments, costs and categories go; contributions are kept untied")

        # 7c2. Expenses and payments that add up (PD-013 step 1, B65; B45 for the date).
        print("7c2. Verifying expenses: cost basis, statuses, refundable, archive, links...")
        import datetime as _dt
        real_budget_today = budget_module._today
        budget_module._today = lambda: _dt.date(2026, 11, 20)  # pinned Chicago "today"
        try:
            exp_cat = c.post(f"{b_url}/categories", json={"name": "Placeholder Venue"},
                             headers=headers).json()["id"]
            vendor = c.post(f"/api/v1/weddings/{wedding_id}/vendors", headers=headers, json={
                "section": "venue", "name": "Sample Loft", "contact_name": "Placeholder Person",
                "email": "loft@example.test", "phone": "(555) 010-0199"})
            assert vendor.status_code == 201, vendor.text
            vendor_id = vendor.json()["id"]
            res = c.post(f"{b_url}/categories/{exp_cat}/costs", headers=headers, json={
                "vendor_name": "Sample Loft", "estimated_cents": 1_000_000,
                "couple_vendor_id": vendor_id, "contract_status": "sent",
                "payment_method": "  Check ", "notes": "  Placeholder note \n",
                "link_url": "https://drive.example.test/file/d/abc"})
            assert res.status_code == 201, res.text
            loft = res.json()["id"]
            assert (res.json()["payment_method"], res.json()["notes"]) == (
                "Check", "Placeholder note"), "text tidied, blank means none"
            for bad in ("javascript:alert(1)", "data:text/html,x", "ftp://example.test/x",
                        "https://", "drive.example.test/file", "https://a b.test",
                        "http://[broken", "https://drive.google.com@other.example.test/x",
                        "https://example.test/a\x07b"):
                res = c.patch(f"{b_url}/costs/{loft}", json={"link_url": bad}, headers=headers)
                assert res.status_code == 422, (bad, res.status_code)
            assert c.patch(f"{b_url}/costs/{loft}", json={"contract_status": "accepted"},
                           headers=headers).status_code == 422
            assert c.patch(f"{b_url}/costs/{loft}", json={"final_cents": -1},
                           headers=headers).status_code == 422
            assert c.patch(f"{b_url}/costs/{loft}", json={"couple_vendor_id": "nope"},
                           headers=headers).status_code == 404

            def expense(cost_id):
                ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
                cat = next(k for k in ov["categories"] if k["id"] == exp_cat)
                return ov, cat, next(x for x in cat["costs"] if x["id"] == cost_id)

            ov, cat, cost = expense(loft)
            assert ov["today"] == "2026-11-20", "overdue is measured against Chicago's date"
            assert cost["vendor"] == {"id": vendor_id, "name": "Sample Loft",
                                      "section": "venue"}, "name and section, no contacts"
            assert "loft@example.test" not in str(ov) and "555" not in str(ov)
            assert (cost["committed_cents"], cost["committed_basis"], cost["status"]) == (
                1_000_000, "estimate", "unpaid")
            # The cost is the final cost, else the quote, else the estimate.
            c.patch(f"{b_url}/costs/{loft}", json={"quoted_cents": 1_100_000}, headers=headers)
            assert expense(loft)[2]["committed_basis"] == "quote"
            c.patch(f"{b_url}/costs/{loft}", json={"final_cents": 1_200_000}, headers=headers)
            ov, cat, cost = expense(loft)
            assert (cost["committed_cents"], cost["committed_basis"]) == (1_200_000, "final")
            assert (cat["committed_basis"], ov["totals"]["committed_basis"]) == ("final", "final")

            def pay(body):
                res = c.post(f"{b_url}/costs/{loft}/payments", json=body, headers=headers)
                assert res.status_code == 201, res.text
                return res.json()

            first = pay({"kind": "deposit", "amount_cents": 600_000, "due_on": "2026-11-11",
                         "method": "Check", "reference": " No. 101 "})
            second = pay({"amount_cents": 600_000, "due_on": "2027-09-23"})
            security = pay({"kind": "deposit", "amount_cents": 200_000, "due_on": "2027-09-23",
                            "refundable": True, "link_url": "http://drive.example.test/x"})
            assert (first["reference"], first["paid"], first["overdue"]) == ("No. 101", False, True)
            assert security["refundable"] is True and security["would_overpay_cents"] == 0
            ov, cat, cost = expense(loft)
            assert cost["status"] == "overdue", "an unpaid payment due before today"
            assert (cost["scheduled_cents"], cost["refundable_cents"], cost["paid_cents"],
                    cost["remaining_cents"], cost["over_scheduled_cents"]) == (
                1_200_000, 200_000, 0, 1_200_000, 0), cost
            due = [d for d in ov["next_due"] if d["cost_id"] == loft]
            assert [(d["amount_cents"], d["overdue"], d["refundable"]) for d in due] == [
                (600_000, True, False), (600_000, False, False), (200_000, False, True)], due

            # Partly paid: one ticked, with the day it was paid; a future day is refused.
            first_url = f"{b_url}/payments/{first['id']}/paid"
            assert c.put(first_url, json={"paid": True, "paid_on": "2026-11-21"},
                         headers=headers).status_code == 422, "the date paid can't be ahead"
            assert c.put(first_url, json={"paid": False, "paid_on": "2026-11-10"},
                         headers=headers).status_code == 422
            res = c.put(first_url, json={"paid": True, "paid_on": "2026-11-10"}, headers=headers)
            assert res.status_code == 200 and res.json()["paid_on"] == "2026-11-10", res.text
            assert res.json()["overdue"] is False
            ov, cat, cost = expense(loft)
            assert (cost["status"], cost["paid_cents"], cost["remaining_cents"]) == (
                "partly_paid", 600_000, 600_000), cost
            # Refundable money is tracked, never counted as paid toward the cost.
            c.put(f"{b_url}/payments/{security['id']}/paid", json={"paid": True}, headers=headers)
            ov, cat, cost = expense(loft)
            assert (cost["paid_cents"], cost["refundable_paid_cents"]) == (600_000, 200_000)
            assert (cat["refundable_cents"], cat["refundable_paid_cents"]) == (200_000, 200_000)
            assert cost["status"] == "partly_paid"
            # The warning before overpaying: ticking the balance is fine; a further
            # payment would take paid over the cost, and the overview says by how much.
            assert next(p for p in cost["payments"] if p["id"] == second["id"])[
                "would_overpay_cents"] == 0
            extra = pay({"amount_cents": 50_000})
            ov, cat, cost = expense(loft)
            assert cost["over_scheduled_cents"] == 50_000, "payments add up to more than the cost"
            assert next(p for p in cost["payments"] if p["id"] == extra["id"])[
                "would_overpay_cents"] == 0, "not while the balance is unticked"
            c.put(f"{b_url}/payments/{second['id']}/paid", json={"paid": True}, headers=headers)
            ov, cat, cost = expense(loft)
            assert cost["status"] == "partly_paid", "an unticked payment is still on it"
            assert next(p for p in cost["payments"] if p["id"] == extra["id"])[
                "would_overpay_cents"] == 50_000
            res = c.put(f"{b_url}/payments/{extra['id']}/paid", json={"paid": True},
                        headers=headers)
            assert res.status_code == 200, "a warning, not a block"
            ov, cat, cost = expense(loft)
            assert (cost["status"], cost["paid_cents"], cost["overpaid_cents"],
                    cost["remaining_cents"]) == ("paid", 1_250_000, 50_000, 0), cost
            # Edit and delete: the figures follow at once.
            assert c.delete(f"{b_url}/payments/{extra['id']}", headers=headers).status_code == 204
            ov, cat, cost = expense(loft)
            assert (cost["status"], cost["paid_cents"], cost["overpaid_cents"]) == (
                "paid", 1_200_000, 0), cost
            c.patch(f"{b_url}/payments/{second['id']}", json={"amount_cents": 500_000},
                    headers=headers)
            ov, cat, cost = expense(loft)
            assert (cost["status"], cost["paid_cents"], cost["remaining_cents"]) == (
                "partly_paid", 1_100_000, 100_000), "paid no longer covers the cost"
            assert c.patch(f"{b_url}/payments/{second['id']}", json={"paid_on": "2026-11-19"},
                           headers=headers).json()["paid_on"] == "2026-11-19"
            res = c.put(f"{b_url}/payments/{second['id']}/paid", json={"paid": False},
                        headers=headers)
            assert res.json()["paid_on"] is None, "unticking clears the date paid"
            assert c.patch(f"{b_url}/payments/{second['id']}", json={"paid_on": "2026-11-19"},
                           headers=headers).status_code == 422, "no date paid while unpaid"
            assert c.patch(f"{b_url}/payments/{second['id']}", json={"paid": True},
                           headers=headers).json()["paid"] is False, "editing never ticks"

            # Archive: kept, still listed, but out of every total and the due list.
            before = c.get(f"{b_url}/overview", headers=headers).json()["totals"]
            assert c.patch(f"{b_url}/costs/{loft}", json={"archived": True},
                           headers=headers).status_code == 200
            ov, cat, cost = expense(loft)
            assert cost["archived"] is True and len(cost["payments"]) == 3
            assert (cat["committed_cents"], cat["paid_cents"], cat["refundable_cents"]) == (0, 0, 0)
            assert ov["totals"]["committed_cents"] == before["committed_cents"] - 1_200_000
            assert ov["totals"]["paid_cents"] == before["paid_cents"] - 600_000
            assert all(d["cost_id"] != loft for d in ov["next_due"])
            c.patch(f"{b_url}/costs/{loft}", json={"archived": False}, headers=headers)
            assert c.get(f"{b_url}/overview", headers=headers).json()["totals"] == before

            # Viewers can't change any of the new fields.
            for method, url, body in (
                ("patch", f"{b_url}/costs/{loft}", {"archived": True}),
                ("patch", f"{b_url}/costs/{loft}", {"contract_status": "signed"}),
                ("patch", f"{b_url}/payments/{first['id']}", {"refundable": True}),
                ("put", first_url, {"paid": True, "paid_on": "2026-11-01"}),
            ):
                assert c.request(method.upper(), url, json=body,
                                 headers=viewer_headers).status_code == 403, (method, url)
            # Removing the vendor from the Vendors page keeps the expense, unlinked.
            assert c.delete(f"/api/v1/weddings/{wedding_id}/vendors/{vendor_id}",
                            headers=headers).status_code == 204
            assert expense(loft)[2]["vendor"] is None
            with Session(sync_engine) as s:
                from app.db.models import BudgetCost as _BudgetCostRow
                assert s.get(_BudgetCostRow, loft).couple_vendor_id is None, \
                    "the link itself is cleared, not just hidden"
            clear_category(exp_cat)

            # The status describes the cost, so refundable deposits never move it to
            # paid or partly paid (the badge always agrees with "Paid").
            from types import SimpleNamespace as _Row
            from app.utils.budget_math import cost_figures

            def _status(cost, *pays):
                rows = [_Row(id=str(i), amount_cents=a, paid=p, refundable=r, due_on=None)
                        for i, (a, p, r) in enumerate(pays)]
                return cost_figures(_Row(final_cents=None, quoted_cents=cost,
                                         estimated_cents=None), rows, _dt.date(2026, 11, 20))
            f = _status(1_200_000, (200_000, True, True))
            assert (f.status, f.paid_cents) == ("unpaid", 0), "only the deposit ticked"
            f = _status(1_200_000, (1_200_000, True, False), (200_000, False, True))
            assert (f.status, f.remaining_cents) == ("paid", 0), "deposit left to pay"
            assert _status(None, (200_000, True, True)).status == "unpaid", "no cost yet"
            assert _status(None).status == "unpaid"
        finally:
            budget_module._today = real_budget_today
        print("   * Expenses: final, else quote, else estimate; unpaid, partly paid, paid, "
              "overdue on Chicago's date; refundable kept out; overpay warned; archive kept "
              "out of totals; links checked; viewers read only")

        # 7c3. The dashboard and moving money between categories (PD-013 step 2, B66).
        print("7c3. Verifying the budget dashboard, targets, contingency and moving money...")
        from app.utils.budget_math import dashboard_figures, target_figures, target_state
        # Each category against its target: blank, zero, near (90%+), at, over.
        assert target_state(None, 5) == "no_target"
        assert (target_state(0, 0), target_state(0, 1)) == ("within", "over"), "zero target"
        assert (target_state(1000, 899), target_state(1000, 900)) == ("within", "near_limit")
        assert (target_state(1000, 1000), target_state(1000, 1001)) == ("near_limit", "over")
        f = target_figures(None, 5_000, 100_000)
        assert (f["share_pct"], f["target_left_cents"], f["over_target_cents"],
                f["used_pct"]) == (None, None, 0, None), "a blank target has no share or left"
        f = target_figures(0, 0, 100_000)
        assert (f["state"], f["share_pct"], f["used_pct"], f["target_left_cents"]) == (
            "within", 0, None, 0), "a 0 target: nothing to divide by"
        f = target_figures(25_000, 30_000, None)
        assert (f["state"], f["share_pct"], f["target_left_cents"], f["over_target_cents"],
                f["used_pct"]) == ("over", None, 0, 5_000, 120), "no total: no share"
        assert target_figures(1, 0, 300)["share_pct"] == 0
        assert target_figures(150, 0, 300)["share_pct"] == 50
        assert target_figures(1, 0, 200)["share_pct"] == 1, "a half percent rounds up"
        # The whole budget: a blank total is "not set", never $0 or over.
        d = dashboard_figures(None, 50_000, 40_000, 10_000, ["over", "within"])
        assert (d["budget_state"], d["left_of_total_cents"], d["over_total_cents"],
                d["unallocated_cents"], d["allocated_pct"], d["committed_pct"]) == (
            "not_set", None, None, None, None, None), d
        assert (d["paid_toward_cost_cents"], d["paid_pct"], d["categories_over"]) == (
            30_000, 75, 1)
        d = dashboard_figures(100_000, 120_000, 0, 0, [])
        assert (d["budget_state"], d["left_of_total_cents"], d["paid_pct"],
                d["unallocated_cents"], d["over_allocated_cents"], d["allocated_pct"]) == (
            "within", 100_000, None, 0, 20_000, 120), "nothing committed: no paid share"
        d = dashboard_figures(100_000, 0, 130_000, 40_000, [])
        assert (d["budget_state"], d["over_total_cents"], d["left_of_total_cents"],
                d["committed_pct"]) == ("over", 30_000, 0, 130)
        assert dashboard_figures(100_000, 0, 95_000, 0, [])["budget_state"] == "near_limit"
        # Overpaid: paid toward the cost counts each expense up to its cost, so one
        # vendor overpaid never shows the budget as further along than it is.
        rows = [_Row(id="a", amount_cents=15_000, paid=True, refundable=False, due_on=None)]
        over = cost_figures(_Row(final_cents=None, quoted_cents=10_000, estimated_cents=None),
                            rows, _dt.date(2026, 11, 20))
        owed = cost_figures(_Row(final_cents=None, quoted_cents=10_000, estimated_cents=None),
                            [], _dt.date(2026, 11, 20))
        committed_sum = over.committed_cents + owed.committed_cents
        remaining_sum = over.remaining_cents + owed.remaining_cents
        d = dashboard_figures(None, 0, committed_sum, remaining_sum, [])
        assert (d["paid_toward_cost_cents"], d["paid_pct"]) == (10_000, 50), d
        print("   * Calculations: blank total, zero targets, near limit at 90%, over, overpaid")

        # Through the API: a category's target, share and status, refundable and
        # archived money kept out, the counts, and the contingency found by name.
        assert c.put(f"{b_url}/total", json={"total_cents": 10_000_000},
                     headers=headers).status_code == 200
        dash_a = c.post(f"{b_url}/categories", json={"name": "Sample Florals B66",
                                                    "planned_cents": 1_000_000},
                        headers=headers).json()["id"]
        dash_b = c.post(f"{b_url}/categories", json={"name": "Sample Music B66"},
                        headers=headers).json()["id"]
        florist = c.post(f"{b_url}/categories/{dash_a}/costs", headers=headers, json={
            "vendor_name": "Sample Florist", "quoted_cents": 950_000}).json()["id"]
        c.post(f"{b_url}/costs/{florist}/payments", headers=headers,
               json={"amount_cents": 100_000, "due_on": "2099-01-01", "refundable": True})
        old = c.post(f"{b_url}/categories/{dash_a}/costs", headers=headers, json={
            "vendor_name": "Sample Old Quote", "quoted_cents": 5_000_000}).json()["id"]
        c.patch(f"{b_url}/costs/{old}", json={"archived": True}, headers=headers)

        def dash():
            ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
            return ov, {k["id"]: k for k in ov["categories"]}

        ov, cats = dash()
        a = cats[dash_a]
        assert (a["committed_cents"], a["state"], a["share_pct"], a["target_left_cents"],
                a["used_pct"], a["expense_count"]) == (
            950_000, "near_limit", 10, 50_000, 95, 1), "archived and refundable kept out"
        assert (cats[dash_b]["state"], cats[dash_b]["share_pct"]) == ("no_target", None)
        assert ov["dashboard"]["contingency_id"] is None
        t, d = ov["totals"], ov["dashboard"]
        assert d["left_of_total_cents"] == max(t["total_cents"] - t["committed_cents"], 0)
        assert d["expense_count"] == sum(k["expense_count"] for k in ov["categories"])
        assert d["upcoming_count"] + d["overdue_count"] == len(ov["next_due"])
        assert d["upcoming_count"] >= 1, "the refundable deposit is still coming up"
        print("   * Categories: target, share of the total, left, status; counts add up")

        # Contingency: found by name (no database change), offered, never made for them.
        cont = c.post(f"{b_url}/categories", json={"name": "  CONTINGENCY "},
                      headers=headers).json()["id"]
        ov, cats = dash()
        assert ov["dashboard"]["contingency_id"] == cont and cats[cont]["is_contingency"]
        assert not cats[dash_a]["is_contingency"]

        # Moving money changes the two targets together, never below 0.
        move = f"{b_url}/move"
        res = c.post(move, headers=headers, json={"from_category_id": dash_a,
                                                  "to_category_id": cont,
                                                  "amount_cents": 40_000})
        assert res.status_code == 200, res.text
        moved = {k["id"]: k for k in res.json()["categories"]}
        assert (moved[dash_a]["planned_cents"], moved[cont]["planned_cents"]) == (
            960_000, 40_000), "a blank target counts as 0 when money moves in"
        assert moved[dash_a]["state"] == "near_limit"
        total_before = res.json()["totals"]["planned_cents"]
        for body, code in (
            ({"from_category_id": dash_a, "to_category_id": cont,
              "amount_cents": 960_001}, 409),
            ({"from_category_id": dash_b, "to_category_id": cont, "amount_cents": 1}, 409),
            ({"from_category_id": dash_a, "to_category_id": dash_a, "amount_cents": 1}, 422),
            ({"from_category_id": dash_a, "to_category_id": cont, "amount_cents": 0}, 422),
            ({"from_category_id": dash_a, "to_category_id": cont, "amount_cents": -5}, 422),
            ({"from_category_id": dash_a, "to_category_id": "nope", "amount_cents": 1}, 404),
        ):
            assert c.post(move, headers=headers, json=body).status_code == code, body
        # Atomic: when money can't go in (the target would be too large), none comes out.
        with Session(sync_engine) as s:
            from app.db.models import BudgetCategory as _Cat
            s.get(_Cat, dash_b).planned_cents = 1_000_000_000
            s.commit()
        res = c.post(move, headers=headers, json={"from_category_id": dash_a,
                                                  "to_category_id": dash_b,
                                                  "amount_cents": 1})
        assert res.status_code == 422, res.text
        ov, cats = dash()
        assert (cats[dash_a]["planned_cents"], cats[dash_b]["planned_cents"]) == (
            960_000, 1_000_000_000), "a refused move changes neither target"
        with Session(sync_engine) as s:
            s.get(_Cat, dash_b).planned_cents = None
            s.commit()
        # Moving out all of it leaves 0, and the total target is unchanged by moves.
        res = c.post(move, headers=headers, json={"from_category_id": cont,
                                                  "to_category_id": dash_a,
                                                  "amount_cents": 40_000})
        moved = {k["id"]: k for k in res.json()["categories"]}
        assert (moved[cont]["planned_cents"], moved[dash_a]["planned_cents"]) == (0, 1_000_000)
        assert res.json()["totals"]["planned_cents"] == total_before
        # Viewers and outsiders can't move money; another wedding's ids aren't found.
        for h in (viewer_headers, unauth_headers):
            assert c.post(move, headers=h, json={"from_category_id": dash_a,
                                                 "to_category_id": cont,
                                                 "amount_cents": 1}).status_code == 403
        for k in (dash_a, dash_b, cont):
            clear_category(k)
        assert c.put(f"{b_url}/total", json={"total_cents": None},
                     headers=headers).status_code == 200
        print("   * Move money: both targets in one step, never below 0, refused moves "
              "change nothing; contingency by name; viewers read only")

        # Another wedding's budget rows can't be read, changed or linked through this
        # wedding's URLs, even with real ids. couple_2 owns the seeded second wedding.
        other_headers = {"Authorization": "Bearer mock-couple_2"}
        o_url = "/api/v1/weddings/wedding_planning_test/budget"
        o_cat = c.post(f"{o_url}/categories", json={"name": "Their venue"},
                       headers=other_headers)
        assert o_cat.status_code == 201, o_cat.text
        o_cat = o_cat.json()["id"]
        o_cost = c.post(f"{o_url}/categories/{o_cat}/costs", json={"vendor_name": "Their hall"},
                        headers=other_headers).json()["id"]
        o_pay = c.post(f"{o_url}/costs/{o_cost}/payments", json={"amount_cents": 100},
                       headers=other_headers).json()["id"]
        o_con = c.post(f"{o_url}/contributions", json={"contributor": "Their family",
                       "amount_cents": 100}, headers=other_headers).json()["id"]
        o_vendor = c.post("/api/v1/weddings/wedding_planning_test/vendors", headers=other_headers,
                          json={"section": "venue", "name": "Their loft"})
        assert o_vendor.status_code == 201, o_vendor.text
        o_vendor = o_vendor.json()["id"]
        mine = c.post(f"{b_url}/categories", json={"name": "Mine"}, headers=headers).json()["id"]
        my_cost = c.post(f"{b_url}/categories/{mine}/costs", json={"vendor_name": "My hall"},
                         headers=headers).json()["id"]
        my_con = c.post(f"{b_url}/contributions", json={"contributor": "My family",
                        "amount_cents": 100}, headers=headers).json()["id"]
        cross = [
            ("patch", f"{b_url}/categories/{o_cat}", {"name": "Taken"}),
            ("delete", f"{b_url}/categories/{o_cat}", None),
            ("post", f"{b_url}/categories/{o_cat}/costs", {"vendor_name": "Z"}),
            ("patch", f"{b_url}/costs/{o_cost}", {"quoted_cents": 1}),
            ("delete", f"{b_url}/costs/{o_cost}", None),
            ("post", f"{b_url}/costs/{o_cost}/payments", {"amount_cents": 1}),
            ("patch", f"{b_url}/payments/{o_pay}", {"amount_cents": 1}),
            ("put", f"{b_url}/payments/{o_pay}/paid", {"paid": True}),
            ("delete", f"{b_url}/payments/{o_pay}", None),
            ("patch", f"{b_url}/contributions/{o_con}", {"amount_cents": 1}),
            ("delete", f"{b_url}/contributions/{o_con}", None),
            ("patch", f"{b_url}/costs/{my_cost}", {"category_id": o_cat}),
            ("patch", f"{b_url}/costs/{my_cost}", {"couple_vendor_id": o_vendor}),
            ("post", f"{b_url}/categories/{mine}/costs",
             {"vendor_name": "Z", "couple_vendor_id": o_vendor}),
            ("post", f"{b_url}/contributions",
             {"contributor": "Z", "amount_cents": 1, "category_id": o_cat}),
            ("patch", f"{b_url}/contributions/{my_con}", {"category_id": o_cat}),
            ("post", f"{b_url}/move",
             {"from_category_id": o_cat, "to_category_id": mine, "amount_cents": 1}),
            ("post", f"{b_url}/move",
             {"from_category_id": mine, "to_category_id": o_cat, "amount_cents": 1}),
        ]
        for method, url, body in cross:
            kwargs = {"headers": headers}
            if body is not None:
                kwargs["json"] = body
            res = c.request(method.upper(), url, **kwargs)
            assert res.status_code == 404, (method, url, res.status_code)
        theirs = c.get(f"{o_url}/overview", headers=other_headers).json()
        assert [cat["name"] for cat in theirs["categories"]] == ["Their venue"]
        assert theirs["categories"][0]["planned_cents"] is None, "no money moved in or out"
        their_pay = theirs["categories"][0]["costs"][0]["payments"][0]
        assert (their_pay["amount_cents"], their_pay["paid"]) == (100, False)
        assert [con["amount_cents"] for con in theirs["contributions"]] == [100]
        ours = c.get(f"{b_url}/overview", headers=headers).json()
        assert all(cat["id"] != o_cat for cat in ours["categories"])
        assert next(cat for cat in ours["categories"] if cat["id"] == mine)["costs"][0][
            "id"] == my_cost, "the cost stayed in this wedding's category"
        assert all(con["category_id"] is None for con in ours["contributions"])
        print("   * Cross-wedding: another wedding's real ids are refused (404) and untouched")

        # 7c4. Categories and the expense list (PD-013 step 3, B67).
        print("7c4. Verifying default categories, order, duplicate and removing a category...")
        from app.utils.budget_defaults import DEFAULT_NAMES
        for k in c.get(f"{b_url}/overview", headers=headers).json()["categories"]:
            clear_category(k["id"])
        # Earlier steps removed suggested categories (Contingency); start from none
        # removed, as a new wedding does (B71).
        assert c.post(f"{b_url}/categories/defaults/restore",
                      headers=headers).status_code == 200
        # The couple's own venue category, under a look-alike name, holding an expense.
        venue_own = c.post(f"{b_url}/categories", headers=headers, json={
            "name": " venue  and CATERING", "planned_cents": 900_000}).json()["id"]
        hall = c.post(f"{b_url}/categories/{venue_own}/costs", headers=headers, json={
            "vendor_name": "Sample Hall", "quoted_cents": 500_000}).json()["id"]
        mine = c.post(f"{b_url}/categories", json={"name": "Mine"}, headers=headers).json()["id"]
        ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
        assert ov["missing_default_categories"] == [n for n in DEFAULT_NAMES
                                                    if n != "Venue"], ov
        assert c.post(f"{b_url}/categories/defaults", headers=headers,
                      json={"names": ["Nope"]}).status_code == 422
        res = c.post(f"{b_url}/categories/defaults", headers=editor_headers)
        assert res.status_code == 200, res.text
        assert res.json() == {"added": [n for n in DEFAULT_NAMES if n != "Venue"],
                              "already_had": ["Venue"]}, res.json()
        ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
        names = [k["name"] for k in ov["categories"]]
        assert names == ["venue and CATERING", "Mine"] + res.json()["added"], \
            "added after the couple's own, in the suggested order"
        assert len(ov["categories"]) == 12 and ov["missing_default_categories"] == []
        by_name = {k["name"]: k for k in ov["categories"]}
        own = by_name["venue and CATERING"]
        assert (own["id"], own["planned_cents"], [x["id"] for x in own["costs"]]) == (
            venue_own, 900_000, [hall]), "an existing category and its expense stay as they are"
        assert all(by_name[n]["planned_cents"] is None for n in res.json()["added"]), \
            "no target is invented"
        assert by_name["Contingency"]["is_contingency"] is True
        ceremony = by_name["Ceremony & Legal"]["suggestions"]
        assert {"Ketubah", "Chuppah", "Rabbi's fee", "Officiant"} <= set(ceremony), ceremony
        assert own["suggestions"][:2] == ["Ceremony venue", "Reception venue"]
        # PD-015: catering has its own category, so it isn't offered under Venue too.
        assert "Catering" not in own["suggestions"], own["suggestions"]
        food = by_name["Food & Drink"]["suggestions"]
        assert food == ["Catering", "Bar and beverages", "Wedding cake and desserts",
                        "Cocktail hour", "Late-night food", "Service charge and gratuity",
                        "Catering rentals"], food
        assert by_name["Mine"]["suggestions"] == [] and by_name["Contingency"]["suggestions"] == []
        again = c.post(f"{b_url}/categories/defaults", headers=headers, json={})
        assert again.json() == {"added": [], "already_had": list(DEFAULT_NAMES)}, again.json()
        assert len(c.get(f"{b_url}/overview", headers=headers).json()["categories"]) == 12, \
            "a second click adds nothing"
        # Adding or renaming uses the same rule, so look-alikes can't be made by hand.
        for name in ("Flowers and Decor", "venues", " ceremony AND legal "):
            res = c.post(f"{b_url}/categories", json={"name": name}, headers=headers)
            assert res.status_code == 409, (name, res.status_code)
        assert c.patch(f"{b_url}/categories/{mine}", json={"name": "Venue"},
                       headers=headers).status_code == 409
        # Only one of them: a couple who removed Other can add just it back.
        other = by_name["Other"]["id"]
        assert c.delete(f"{b_url}/categories/{other}", headers=headers).status_code == 204
        res = c.post(f"{b_url}/categories/defaults", headers=headers,
                     json={"names": ["other", "Contingency"]})
        assert res.json() == {"added": ["Other"], "already_had": ["Contingency"]}, res.json()
        assert c.post(f"{b_url}/categories/defaults",
                      headers=viewer_headers).status_code == 403
        print("   * Default categories: on the couple's click only, after their own, no "
              "targets; look-alike names kept, never doubled; suggestions per category")

        # B71: a suggestion the couple remove isn't offered again until they ask.
        def offered():
            ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
            return ov["missing_default_categories"], ov["removed_default_categories"]
        assert offered() == ([], []), "Other, removed and named back above, isn't declined"
        assert c.delete(f"{b_url}/categories/{by_name['Contingency']['id']}",
                        headers=editor_headers).status_code == 204
        assert offered() == ([], ["Contingency"]), offered()
        flowers_id = by_name["Flowers & Decor"]["id"]
        assert c.delete(f"{b_url}/categories/{flowers_id}", headers=headers).status_code == 204
        assert offered() == ([], ["Flowers & Decor", "Contingency"]), offered()
        # A rename away isn't a removal: with none of that name left, it's offered.
        ceremony_id = by_name["Ceremony & Legal"]["id"]
        assert c.patch(f"{b_url}/categories/{ceremony_id}", json={"name": "Our ceremony"},
                       headers=headers).status_code == 200
        assert offered() == (["Ceremony & Legal"], ["Flowers & Decor", "Contingency"])
        res = c.post(f"{b_url}/categories/defaults", headers=headers)
        assert res.json()["added"] == ["Ceremony & Legal"], \
            "adding all the suggestions leaves out the removed ones"
        assert offered() == ([], ["Flowers & Decor", "Contingency"])
        for body in ({"names": ["Nope"]}, {"names": []}):
            assert c.post(f"{b_url}/categories/defaults/restore", headers=headers,
                          json=body).status_code == 422, body
        assert c.post(f"{b_url}/categories/defaults/restore", headers=viewer_headers,
                      json={"names": ["Contingency"]}).status_code == 403
        assert offered() == ([], ["Flowers & Decor", "Contingency"]), "viewers change nothing"
        res = c.post(f"{b_url}/categories/defaults/restore", headers=headers,
                     json={"names": [" contingency"]})
        assert res.status_code == 200 and res.json() == {"restored": ["Contingency"]}, res.text
        assert offered() == (["Contingency"], ["Flowers & Decor"]), offered()
        # Adding one back by hand makes it theirs again; removing it again counts again.
        res = c.post(f"{b_url}/categories", json={"name": "Flowers and Decor"}, headers=headers)
        assert res.status_code == 201, res.text
        assert offered() == (["Contingency"], [])
        assert c.delete(f"{b_url}/categories/{res.json()['id']}",
                        headers=headers).status_code == 204
        assert offered() == (["Contingency"], ["Flowers & Decor"])
        res = c.post(f"{b_url}/categories/defaults/restore", headers=editor_headers)
        assert res.json() == {"restored": ["Flowers & Decor"]}, res.json()
        assert offered() == (["Flowers & Decor", "Contingency"], [])
        assert c.post(f"{b_url}/categories/defaults/restore",
                      headers=headers).json() == {"restored": []}, "nothing left to restore"
        # Naming a removed one adds it back and forgets the removal.
        legal_id = next(k["id"] for k in c.get(f"{b_url}/overview", headers=headers).json()[
            "categories"] if k["name"] == "Ceremony & Legal")
        assert c.delete(f"{b_url}/categories/{legal_id}", headers=headers).status_code == 204
        assert offered() == (["Flowers & Decor", "Contingency"], ["Ceremony & Legal"])
        res = c.post(f"{b_url}/categories/defaults", headers=headers,
                     json={"names": ["Ceremony & Legal", "Flowers & Decor", "Contingency"]})
        assert res.json()["added"] == ["Flowers & Decor", "Ceremony & Legal", "Contingency"]
        assert offered() == ([], [])
        assert c.delete(f"{b_url}/categories/{ceremony_id}", headers=headers).status_code == 204
        assert offered() == ([], []), "removing a category that isn't a suggestion declines none"
        theirs = c.get(f"{o_url}/overview", headers=other_headers).json()
        assert theirs["removed_default_categories"] == [], "another wedding's list untouched"
        print("   * Removed suggestions: not offered again, the rest still are; a rename "
              "isn't a removal; restored on an editor's click; viewers can't change it")

        # PD-015: "Venue & Catering", the name before Venue and Food & Drink split,
        # still stands for Venue, both as a category and as a removed suggestion.
        from app.utils.budget_defaults import missing_defaults, removed_defaults
        assert DEFAULT_NAMES == (
            "Venue", "Food & Drink", "Photography & Entertainment", "Attire & Beauty",
            "Flowers & Decor", "Planning & Stationery", "Transportation & Accommodation",
            "Ceremony & Legal", "Additional Events", "Other", "Contingency"), DEFAULT_NAMES
        rest = [n for n in DEFAULT_NAMES if n != "Venue"]
        assert missing_defaults(["Venue & Catering"]) == rest, "Venue isn't offered twice"
        assert missing_defaults([" venues "]) == rest
        assert missing_defaults([], ["Venue & Catering"]) == rest, "declined under the old name"
        assert removed_defaults([], ["venue and catering"]) == ["Venue"]
        assert removed_defaults(["Venue"], ["Venue & Catering"]) == []
        assert "Food & Drink" in missing_defaults([], ["Venue & Catering"]), \
            "removing the old venue category doesn't decline the new Food & Drink"
        from app.db.models import Wedding as _Wedding
        with Session(sync_engine) as s:
            s.get(_Wedding, wedding_id).declined_budget_defaults = ["Venue & Catering"]
            s.commit()
        assert offered() == ([], []), "they have a venue category, so nothing to restore"
        # The Rename to Venue button is an ordinary rename, allowed over its own old name.
        res = c.patch(f"{b_url}/categories/{venue_own}", json={"name": "Our hall"},
                      headers=headers)
        assert res.status_code == 200, res.text
        assert offered() == ([], ["Venue"]), offered()
        assert c.post(f"{b_url}/categories/defaults/restore", headers=headers,
                      json={"names": ["Venue & Catering"]}).json() == {"restored": ["Venue"]}
        assert offered() == (["Venue"], []), offered()
        res = c.patch(f"{b_url}/categories/{venue_own}", json={"name": "Venue & Catering"},
                      headers=headers)
        assert res.status_code == 200 and offered() == ([], []), res.text
        res = c.patch(f"{b_url}/categories/{venue_own}", json={"name": "Venue"},
                      headers=editor_headers)
        assert res.status_code == 200 and res.json()["name"] == "Venue", res.text
        assert c.patch(f"{b_url}/categories/{venue_own}", json={"name": "Venue & Catering"},
                       headers=viewer_headers).status_code == 403
        after = {k["name"]: k for k in c.get(f"{b_url}/overview", headers=headers).json()[
            "categories"]}
        assert [x["id"] for x in after["Venue"]["costs"]] == [hall], "its expense stays put"
        assert after["Food & Drink"]["costs"] == [], "nothing moves to Food & Drink by itself"
        res = c.post(f"{b_url}/categories", json={"name": "Venue & Catering"}, headers=headers)
        assert res.status_code == 409, "no look-alike of Venue beside it"
        print("   * PD-015: Venue and Food & Drink suggested; the old Venue & Catering name "
              "counts as Venue, kept or declined; renaming it to Venue moves nothing")

        order_url = f"{b_url}/categories/order"
        ids = [k["id"] for k in c.get(f"{b_url}/overview", headers=headers).json()["categories"]]
        wanted = list(reversed(ids))
        assert c.put(order_url, headers=headers, json={"category_ids": wanted}).status_code == 204
        assert [k["id"] for k in c.get(f"{b_url}/overview", headers=viewer_headers).json()[
            "categories"]] == wanted
        for bad in (wanted[1:], wanted + [wanted[0]], wanted[:-1] + [o_cat], []):
            res = c.put(order_url, headers=headers, json={"category_ids": bad})
            assert res.status_code in (409, 422), (bad, res.status_code)
        assert [k["id"] for k in c.get(f"{b_url}/overview", headers=headers).json()[
            "categories"]] == wanted, "a refused order changes nothing"
        newest = c.post(f"{b_url}/categories", json={"name": "Newest"},
                        headers=headers).json()["id"]
        assert c.get(f"{b_url}/overview", headers=headers).json()["categories"][-1][
            "id"] == newest, "a new category goes last"
        assert c.put(order_url, headers=viewer_headers,
                     json={"category_ids": wanted + [newest]}).status_code == 403
        theirs = c.get(f"{o_url}/overview", headers=other_headers).json()
        assert [k["name"] for k in theirs["categories"]] == ["Their venue"], "theirs untouched"
        print("   * Order: the couple's order kept; the list must be complete and theirs; "
              "new ones go last; viewers read only")

        # Duplicate: what was typed is copied; payments and the contract aren't.
        vendor_id = c.post(f"/api/v1/weddings/{wedding_id}/vendors", headers=headers, json={
            "section": "photo_video", "name": "Sample Studio"}).json()["id"]
        src = c.post(f"{b_url}/categories/{mine}/costs", headers=headers, json={
            "vendor_name": "Photographer", "estimated_cents": 300_000, "quoted_cents": 320_000,
            "final_cents": 310_000, "contract_status": "signed", "payment_method": "Check",
            "notes": "Placeholder note", "link_url": "https://drive.example.test/f",
            "couple_vendor_id": vendor_id}).json()["id"]
        paid_pay = c.post(f"{b_url}/costs/{src}/payments", headers=headers, json={
            "kind": "deposit", "amount_cents": 100_000, "due_on": "2026-01-02"}).json()["id"]
        c.put(f"{b_url}/payments/{paid_pay}/paid", json={"paid": True}, headers=headers)
        c.post(f"{b_url}/costs/{src}/payments", headers=headers, json={
            "amount_cents": 50_000, "due_on": "2099-03-01"})
        c.post(f"{b_url}/costs/{src}/payments", headers=headers, json={
            "amount_cents": 50_000, "due_on": "2099-02-01", "refundable": True})
        res = c.post(f"{b_url}/costs/{src}/duplicate", headers=editor_headers)
        assert res.status_code == 201, res.text
        dup = res.json()["id"]
        assert dup != src

        def cost_row(cost_id):
            ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
            return next(x for k in ov["categories"] for x in k["costs"] if x["id"] == cost_id)
        copy, orig = cost_row(dup), cost_row(src)
        assert (copy["category_id"], copy["vendor_name"], copy["estimated_cents"],
                copy["quoted_cents"], copy["final_cents"], copy["payment_method"],
                copy["notes"], copy["link_url"], copy["vendor"]["id"]) == (
            mine, "Photographer (copy)", 300_000, 320_000, 310_000, "Check",
            "Placeholder note", "https://drive.example.test/f", vendor_id), copy
        assert (copy["contract_status"], copy["archived"], copy["payments"],
                copy["paid_cents"], copy["status"], copy["next_due_on"]) == (
            "none", False, [], 0, "unpaid", None), "no payments, nothing paid, no contract"
        assert len(orig["payments"]) == 3 and orig["contract_status"] == "signed"
        assert [p["paid"] for p in orig["payments"] if p["id"] == paid_pay] == [True], \
            "the original's paid tick is untouched"
        assert orig["next_due_on"] == "2099-02-01", "soonest unpaid, refundable included"
        long_name = "x" * 120
        long_id = c.post(f"{b_url}/categories/{mine}/costs", headers=headers,
                         json={"vendor_name": long_name}).json()["id"]
        long_copy = c.post(f"{b_url}/costs/{long_id}/duplicate", headers=headers).json()
        assert len(long_copy["vendor_name"]) == 120 and long_copy["vendor_name"].endswith(
            " (copy)")
        assert c.post(f"{b_url}/costs/{src}/duplicate",
                      headers=viewer_headers).status_code == 403
        assert c.post(f"{b_url}/costs/{o_cost}/duplicate",
                      headers=headers).status_code == 404, "another wedding's expense"
        assert c.post(f"{b_url}/costs/nope/duplicate", headers=headers).status_code == 404
        print("   * Duplicate: copies the costs, method, notes, link and vendor; never "
              "payments, a paid tick or the contract; viewers read only")

        # Removing a category with expenses: refused unless they move; never deleted.
        c.patch(f"{b_url}/costs/{long_id}", json={"archived": True}, headers=headers)
        before = cost_row(src)
        res = c.delete(f"{b_url}/categories/{mine}", headers=headers)
        assert res.status_code == 409 and "4 expenses" in res.json()["detail"], res.text
        assert c.delete(f"{b_url}/categories/{mine}?move_to={mine}",
                        headers=headers).status_code == 422
        assert c.delete(f"{b_url}/categories/{mine}?move_to={o_cat}",
                        headers=headers).status_code == 404, "another wedding's category"
        assert c.delete(f"{b_url}/categories/{mine}?move_to=nope",
                        headers=headers).status_code == 404
        assert cost_row(src)["category_id"] == mine, "a refused removal changes nothing"
        contribution = c.post(f"{b_url}/contributions", headers=headers, json={
            "contributor": "Placeholder family", "amount_cents": 100,
            "category_id": mine}).json()["id"]
        res = c.delete(f"{b_url}/categories/{mine}?move_to={newest}", headers=editor_headers)
        assert res.status_code == 204, res.text
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert mine not in [k["id"] for k in ov["categories"]]
        moved = next(k for k in ov["categories"] if k["id"] == newest)
        assert sorted(x["id"] for x in moved["costs"]) == sorted(
            [src, dup, long_id, long_copy["id"]]), "every expense moved, archived ones too"
        after = cost_row(src)
        assert [(p["id"], p["paid"], p["amount_cents"]) for p in after["payments"]] == [
            (p["id"], p["paid"], p["amount_cents"]) for p in before["payments"]], \
            "payments and paid ticks move unchanged"
        assert next(x for x in ov["contributions"] if x["id"] == contribution)[
            "category_id"] is None, "a contribution towards it stays, untied"
        # An empty category goes without asking where; the viewer still can't.
        empty = c.post(f"{b_url}/categories", json={"name": "Empty"},
                       headers=headers).json()["id"]
        assert c.delete(f"{b_url}/categories/{empty}",
                        headers=viewer_headers).status_code == 403
        assert c.delete(f"{b_url}/categories/{empty}", headers=headers).status_code == 204
        c.delete(f"{b_url}/contributions/{contribution}", headers=headers)
        for k in c.get(f"{b_url}/overview", headers=headers).json()["categories"]:
            clear_category(k["id"])
        assert c.delete(f"/api/v1/weddings/{wedding_id}/vendors/{vendor_id}",
                        headers=headers).status_code == 204
        print("   * Remove a category: refused while it has expenses unless they move; "
              "moved with their payments; never deleted with it")

        # 7c5. Export (PD-013 step 5, B69): one CSV from the same figures as the screen.
        print("7c5. Verifying the budget export: CSV figures, formula guard, toggles, access...")
        import csv as _csv
        import io as _io
        from app.utils.budget_export import dollars as _dollars, safe_cell
        real_budget_today = budget_module._today
        budget_module._today = lambda: _dt.date(2026, 11, 20)
        before_total = c.get(f"{b_url}/overview", headers=headers).json()["totals"]["total_cents"]
        try:
            assert c.put(f"{b_url}/total", json={"total_cents": 3_000_000},
                         headers=headers).status_code == 200
            ex_cat = c.post(f"{b_url}/categories", headers=headers, json={
                "name": "=Placeholder Hall", "planned_cents": 1_500_000}).json()["id"]
            other_cat = c.post(f"{b_url}/categories", headers=headers, json={
                "name": "Placeholder Flowers"}).json()["id"]
            ex_vendor = c.post(f"/api/v1/weddings/{wedding_id}/vendors", headers=headers, json={
                "section": "venue", "name": "Sample Export Hall",
                "website": "https://hall.example.test", "contact_name": "Placeholder Contact",
                "email": "hall@example.test", "phone": "(555) 010-0123"})
            assert ex_vendor.status_code == 201, ex_vendor.text
            ex_vendor_id = ex_vendor.json()["id"]
            hall = c.post(f"{b_url}/categories/{ex_cat}/costs", headers=headers, json={
                "vendor_name": "Sample Export Hall", "final_cents": 1_200_050,
                "couple_vendor_id": ex_vendor_id, "contract_status": "signed",
                "payment_method": "+Check", "notes": "@note, with a comma\nand a new line",
                "link_url": "https://drive.example.test/file/d/hall"}).json()["id"]
            p1 = c.post(f"{b_url}/costs/{hall}/payments", headers=headers, json={
                "kind": "deposit", "amount_cents": 600_000, "due_on": "2026-11-11",
                "reference": "-REF1"}).json()["id"]
            c.post(f"{b_url}/costs/{hall}/payments", headers=headers, json={
                "amount_cents": 600_050, "due_on": "2026-11-01"})
            c.post(f"{b_url}/costs/{hall}/payments", headers=headers, json={
                "kind": "deposit", "amount_cents": 200_000, "due_on": "2027-09-23",
                "refundable": True})
            assert c.put(f"{b_url}/payments/{p1}/paid", headers=headers,
                         json={"paid": True, "paid_on": "2026-11-05"}).status_code == 200
            c.post(f"{b_url}/categories/{other_cat}/costs", headers=headers, json={
                "vendor_name": "Placeholder Florist", "estimated_cents": 250_000})
            gone = c.post(f"{b_url}/categories/{other_cat}/costs", headers=headers, json={
                "vendor_name": "Archived Placeholder", "quoted_cents": 99_900}).json()["id"]
            c.post(f"{b_url}/costs/{gone}/payments", headers=headers,
                   json={"amount_cents": 10_000, "due_on": "2026-12-01"})
            assert c.patch(f"{b_url}/costs/{gone}", json={"archived": True},
                           headers=headers).status_code == 200

            def export(query="", who=None):
                return c.get(f"{b_url}/export.csv{query}", headers=who or headers)

            def sections(res):
                assert res.status_code == 200, res.text
                text = res.content.decode("utf-8")
                assert text.startswith("\ufeff"), "UTF-8 marker for Excel"
                out, heads, current = {}, {}, None
                for row in _csv.reader(_io.StringIO(text.lstrip("\ufeff"))):
                    if not row:
                        continue
                    if row[0] == "Section":
                        current = row
                        continue
                    heads[row[0]] = current
                    out.setdefault(row[0], []).append(dict(zip(current, row)))
                return out, heads

            res = export()
            assert res.headers["content-type"].startswith("text/csv")
            assert res.headers["content-disposition"] == \
                'attachment; filename="wedding-budget-2026-11-20.csv"', "Chicago date"
            assert res.headers["cache-control"] == "no-store"
            got, heads = sections(res)
            ov = c.get(f"{b_url}/overview", headers=headers).json()
            summary = {r["Item"]: r["Value"] for r in got["Summary"]}
            t = ov["totals"]
            assert summary["Currency"] == "USD"
            assert summary["Exported on (Chicago date)"] == "2026-11-20"
            assert summary["Total budget (USD)"] == "30000.00"
            for item, key in (("Committed (USD)", "committed_cents"), ("Paid (USD)", "paid_cents"),
                              ("Still to pay (USD)", "remaining_cents"),
                              ("Overpaid (USD)", "overpaid_cents"),
                              ("Category targets added up (USD)", "planned_cents"),
                              ("Refundable deposits (USD, not part of the cost)",
                               "refundable_cents")):
                assert summary[item] == _dollars(t[key]), (item, summary[item], t[key])
            assert summary["Committed (USD)"] == "14500.50", "archived left out of the totals"
            assert summary["Left of total budget (USD)"] == _dollars(
                ov["dashboard"]["left_of_total_cents"])
            assert summary["Payments overdue"] == str(ov["dashboard"]["overdue_count"]) == "1"
            cats = {r["Category"]: r for r in got["Categories"]}
            assert "'=Placeholder Hall" in cats, "formula-looking names become text"
            for k in ov["categories"]:
                row = cats[safe_cell(k["name"])]
                assert row["Committed (USD)"] == _dollars(k["committed_cents"])
                assert row["Paid (USD)"] == _dollars(k["paid_cents"])
                assert row["Still to pay (USD)"] == _dollars(k["remaining_cents"])
                assert row["Target (USD)"] == _dollars(k["planned_cents"])
            assert cats["'=Placeholder Hall"]["Status"] == "Within target"
            assert cats["'=Placeholder Hall"]["Share of total budget (%)"] == "50"
            expenses = {r["Expense"]: r for r in got["Expenses"]}
            assert set(expenses) == {"Sample Export Hall", "Placeholder Florist"}, \
                "archived expenses left out by default"
            h = expenses["Sample Export Hall"]
            assert (h["Actual (USD)"], h["Cost (USD)"], h["Paid (USD)"],
                    h["Still to pay (USD)"], h["Refundable deposits (USD)"]) == (
                "12000.50", "12000.50", "6000.00", "6000.50", "2000.00")
            assert (h["Linked vendor"], h["Vendor website"], h["Contract"], h["Status"]) == (
                "Sample Export Hall", "https://hall.example.test", "Signed", "Overdue")
            assert h["Payment method"] == "'+Check"
            assert h["Notes"] == "'@note, with a comma\nand a new line", "quoted, kept whole"
            assert h["Link"] == "https://drive.example.test/file/d/hall"
            assert expenses["Placeholder Florist"]["Cost based on"] == "Estimate"
            assert not any("Vendor email" in (hd or []) for hd in heads.values())
            assert b"hall@example.test" not in res.content and b"010-0123" not in res.content
            assert b"Placeholder Contact" not in res.content, "no contacts unless asked"
            pays = [r for r in got["Payments"] if r["Expense"] == "Sample Export Hall"]
            assert len(pays) == 3 and all(r["Expense"] != "Archived Placeholder"
                                          for r in got["Payments"])
            paid_row = next(r for r in pays if r["Paid"] == "Yes")
            assert (paid_row["Amount (USD)"], paid_row["Paid on"], paid_row["Reference"],
                    paid_row["Status"], paid_row["Type"]) == (
                "6000.00", "2026-11-05", "'-REF1", "Paid", "Deposit")
            assert next(r for r in pays if r["Due"] == "2026-11-01")["Status"] == "Overdue"
            assert next(r for r in pays if r["Refundable"] == "Yes")["Amount (USD)"] == "2000.00"
            upcoming = got["Upcoming"]
            assert [(r["Due"], r["Amount (USD)"], r["Status"]) for r in upcoming] == [
                (d["due_on"] or "No date", _dollars(d["amount_cents"]),
                 "Overdue" if d["overdue"] else "Unpaid") for d in ov["next_due"]]
            assert [r["Due"] for r in upcoming] == ["2026-11-01", "2027-09-23"]
            print("   * CSV: summary, categories, expenses, payments and upcoming match "
                  "the overview, in plain dollars")

            got, _ = sections(export("?include_archived=true"))
            arch = {r["Expense"]: r for r in got["Expenses"]}
            assert arch["Archived Placeholder"]["Archived"] == "Yes"
            assert arch["Sample Export Hall"]["Archived"] == "No"
            assert any(r["Expense"] == "Archived Placeholder" for r in got["Payments"])
            assert {r["Item"]: r["Value"] for r in got["Summary"]}["Committed (USD)"] == \
                "14500.50", "listing archived expenses doesn't add them to the totals"
            assert all(r["Expense"] != "Archived Placeholder" for r in got["Upcoming"])
            # As on the screen: an archived expense's payment keeps its own status, but
            # isn't counted among the payments overdue or listed as upcoming.
            gone_pay = next(r for r in got["Payments"] if r["Expense"] == "Archived Placeholder")
            assert (gone_pay["Due"], gone_pay["Status"]) == ("2026-12-01", "Unpaid")
            assert {r["Item"]: r["Value"] for r in got["Summary"]}["Payments overdue"] == "1"
            print("   * Archived expenses: left out unless asked; never in a total")

            res = export("?include_contacts=true")
            got, _ = sections(res)
            h = next(r for r in got["Expenses"] if r["Expense"] == "Sample Export Hall")
            assert (h["Vendor contact"], h["Vendor email"], h["Vendor phone"]) == (
                "Placeholder Contact", "hall@example.test", "(555) 010-0123")
            assert {r["Item"]: r["Value"] for r in got["Summary"]}[
                "Vendor contact details"] == "Included"
            f = next(r for r in got["Expenses"] if r["Expense"] == "Placeholder Florist")
            assert (f["Vendor email"], f["Linked vendor"]) == ("", "")
            print("   * Vendor contacts: only when the box is ticked")

            assert safe_cell("=1+1") == "'=1+1" and safe_cell("\tx") == "'\tx"
            assert safe_cell("  =1") == "'  =1" and safe_cell("\uff1d1") == "'\uff1d1"
            assert safe_cell("Plain") == "Plain" and safe_cell(None) == ""
            assert _dollars(0) == "0.00" and _dollars(5) == "0.05" and _dollars(None) == ""

            for who in (viewer_headers, editor_headers):
                assert export("?include_contacts=true", who).status_code == 200, \
                    "family and editors can download what they can see"
            assert export(who=unauth_headers).status_code == 403
            assert c.get(f"{b_url}/export.csv").status_code in (401, 403)
            print("   * Export access: owners, editors and viewers; nobody outside the list")
        finally:
            budget_module._today = real_budget_today
        for k in c.get(f"{b_url}/overview", headers=headers).json()["categories"]:
            clear_category(k["id"])
        assert c.delete(f"/api/v1/weddings/{wedding_id}/vendors/{ex_vendor_id}",
                        headers=headers).status_code == 204
        assert c.put(f"{b_url}/total", json={"total_cents": before_total},
                     headers=headers).status_code == 200

        print("7c6. Verifying who paid: the payer list, the one-step add, payers on payments...")
        p_url = f"{b_url}/payers"
        assert c.get(f"{b_url}/overview", headers=viewer_headers).json()["payers"] == [], \
            "the list starts empty; no names come from code"
        for who in (viewer_headers, unauth_headers):
            assert c.post(p_url, json={"name": "Z"}, headers=who).status_code == 403
            assert c.patch(f"{p_url}/nope", json={"name": "Z"}, headers=who).status_code == 403
            assert c.delete(f"{p_url}/nope", headers=who).status_code == 403
        res = c.post(p_url, json={"name": "  Sample  Payer A "}, headers=headers)
        assert res.status_code == 201 and res.json() == {
            "id": res.json()["id"], "name": "Sample Payer A", "payment_count": 0}, res.text
        payer_a = res.json()["id"]
        res = c.post(p_url, json={"name": "Placeholder Family"}, headers=editor_headers)
        assert res.status_code == 201, res.text
        payer_b = res.json()["id"]
        assert c.post(p_url, json={"name": "sample payer a"}, headers=headers).status_code == 409
        assert c.post(p_url, json={"name": "   "}, headers=headers).status_code == 422
        assert c.patch(f"{p_url}/{payer_b}", json={"name": "SAMPLE PAYER A"},
                       headers=headers).status_code == 409
        res = c.patch(f"{p_url}/{payer_b}", json={"name": "Placeholder Relatives"},
                      headers=editor_headers)
        assert res.status_code == 200 and res.json()["name"] == "Placeholder Relatives"
        assert c.patch(f"{p_url}/nope", json={"name": "Z"}, headers=headers).status_code == 404
        print("   * People who pay: owners and editors add and rename; duplicates refused; "
              "viewers and outsiders can't")

        pay_cat = c.post(f"{b_url}/categories", json={"name": "Placeholder Music"},
                         headers=headers).json()["id"]

        def costs_in(cat_id):
            ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
            return next(k for k in ov["categories"] if k["id"] == cat_id)["costs"]

        res = c.post(f"{b_url}/categories/{pay_cat}/costs", headers=editor_headers, json={
            "vendor_name": "Sample Band", "quoted_cents": 400_000, "notes": "Two sets",
            "first_payment": {"kind": "deposit", "amount_cents": 100_000,
                              "due_on": "2027-01-10", "payer_id": payer_a}})
        assert res.status_code == 201, res.text
        band = res.json()["id"]
        [cost] = costs_in(pay_cat)
        [first] = cost["payments"]
        assert (first["kind"], first["amount_cents"], first["due_on"], first["paid"],
                first["payer_id"], first["payer_name"]) == (
            "deposit", 100_000, "2027-01-10", False, payer_a, "Sample Payer A"), first
        assert cost["last_payer_id"] == payer_a and cost["notes"] == "Two sets"
        for bad in ({"amount_cents": 0}, {"amount_cents": 1, "payer_id": "nope"},
                    {"amount_cents": 1, "kind": "refund"}):
            res = c.post(f"{b_url}/categories/{pay_cat}/costs", headers=headers,
                         json={"vendor_name": "Half Made", "first_payment": bad})
            assert res.status_code in (404, 422), (bad, res.text)
        assert [k["vendor_name"] for k in costs_in(pay_cat)] == ["Sample Band"], \
            "a refused first payment leaves no half-made expense"
        res = c.post(f"{b_url}/categories/{pay_cat}/costs", headers=headers,
                     json={"vendor_name": "Sample DJ"})
        assert res.status_code == 201
        dj = next(k for k in costs_in(pay_cat) if k["id"] == res.json()["id"])
        assert dj["payments"] == [] and dj["last_payer_id"] is None, "no payment unless asked"
        print("   * Add expense: the expense and its first payment save together, or not at all")

        res = c.post(f"{b_url}/costs/{band}/payments", headers=headers,
                     json={"amount_cents": 300_000, "payer_id": payer_b})
        assert res.status_code == 201 and res.json()["paid"] is False, res.text
        assert res.json()["payer_name"] == "Placeholder Relatives"
        balance = res.json()["id"]
        cost = next(k for k in costs_in(pay_cat) if k["id"] == band)
        assert cost["last_payer_id"] == payer_b, "a new payment starts with the latest payer"
        assert c.post(f"{b_url}/costs/{band}/payments", headers=headers,
                      json={"amount_cents": 1, "payer_id": "nope"}).status_code == 404
        res = c.patch(f"{b_url}/payments/{first['id']}", json={"payer_id": payer_b},
                      headers=editor_headers)
        assert res.status_code == 200 and res.json()["paid"] is False, \
            "choosing who paid never ticks it (rule 4)"
        assert c.put(f"{b_url}/payments/{first['id']}/paid", json={"paid": True},
                     headers=headers).json()["paid"] is True
        res = c.patch(f"{b_url}/payments/{first['id']}", json={"payer_id": payer_a},
                      headers=headers)
        assert res.json()["paid"] is True and res.json()["payer_id"] == payer_a, \
            "changing who paid never unticks it either"
        res = c.patch(f"{b_url}/payments/{balance}", json={"payer_id": None}, headers=headers)
        assert res.json()["payer_id"] is None and res.json()["payer_name"] is None
        assert c.patch(f"{b_url}/payments/{balance}", json={"payer_id": payer_b},
                       headers=viewer_headers).status_code == 403
        print("   * Who paid on payments: chosen, changed and cleared; paid ticks untouched")

        res = c.delete(f"{p_url}/{payer_a}", headers=headers)
        assert res.status_code == 409 and "1 payment" in res.json()["detail"], res.text
        cost = next(k for k in costs_in(pay_cat) if k["id"] == band)
        kept = {pay["id"]: pay["payer_id"] for pay in cost["payments"]}
        assert kept == {first["id"]: payer_a, balance: None}, \
            "a payer named on a payment isn't removed, and no payment is"
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert {p["name"]: p["payment_count"] for p in ov["payers"]} == {
            "Sample Payer A": 1, "Placeholder Relatives": 0}
        assert c.delete(f"{p_url}/{payer_b}", headers=editor_headers).status_code == 204
        print("   * Removing a payer: refused while named on a payment; fine otherwise")

        got, heads = sections(export())
        assert "Who paid" in heads["Payments"] and "How it was paid" in heads["Payments"]
        band_pays = {r["Amount (USD)"]: r for r in got["Payments"] if r["Expense"] == "Sample Band"}
        assert band_pays["1000.00"]["Who paid"] == "Sample Payer A"
        assert band_pays["3000.00"]["Who paid"] == ""
        print("   * Export: each payment says who paid")

        clear_category(pay_cat)

        print("7c7. Verifying tips as their own expense lines (PD-017)...")
        from app.utils.budget_math import percent_of
        assert percent_of(800_000, 2000) == 160_000, "20% of $8,000 is $1,600"
        assert percent_of(1, 5000) == 1 and percent_of(3, 5000) == 2, "half a cent rounds up"
        assert percent_of(33_333, 1875) == 6250 and percent_of(3, 1500) == 0
        assert percent_of(0, 2000) == 0

        tip_cat = c.post(f"{b_url}/categories", json={"name": "Placeholder Food"},
                         headers=headers).json()["id"]
        caterer = c.post(f"{b_url}/categories/{tip_cat}/costs", headers=headers, json={
            "vendor_name": "Sample Caterer", "quoted_cents": 800_000}).json()["id"]
        no_cost = c.post(f"{b_url}/categories/{tip_cat}/costs", headers=headers, json={
            "vendor_name": "Sample Bar"}).json()["id"]

        def tip_costs():
            return {k["id"]: k for k in costs_in(tip_cat)}

        for who in (viewer_headers, unauth_headers):
            assert c.post(f"{b_url}/costs/{caterer}/tips", json={"amount_cents": 100},
                          headers=who).status_code == 403
            assert c.patch(f"{b_url}/tips/nope", json={"amount_cents": 100},
                           headers=who).status_code == 403
        for bad in ({}, {"percent_basis_points": 2000, "amount_cents": 100},
                    {"percent_basis_points": 0}, {"percent_basis_points": 10_001},
                    {"amount_cents": 0}, {"amount_cents": 1, "payer_id": "nope"}):
            res = c.post(f"{b_url}/costs/{caterer}/tips", json=bad, headers=headers)
            assert res.status_code in (404, 422), (bad, res.text)
        assert set(tip_costs()) == {caterer, no_cost}, "a refused tip saves nothing"

        res = c.post(f"{b_url}/costs/{caterer}/tips", headers=editor_headers,
                     json={"percent_basis_points": 2000, "notes": "On the day"})
        assert res.status_code == 201, res.text
        pct_tip = res.json()["id"]
        res = c.post(f"{b_url}/costs/{caterer}/tips", headers=headers, json={
            "amount_cents": 25_000, "due_on": "2027-06-01", "payer_id": payer_a})
        assert res.status_code == 201, res.text
        cash_tip = res.json()["id"]
        k = tip_costs()
        t = k[pct_tip]
        assert (t["vendor_name"], t["category_id"], t["tip_for_cost_id"], t["tip_for_name"],
                t["tip_basis_points"], t["tip_state"], t["tip_base_cents"], t["committed_cents"],
                t["committed_basis"], t["notes"], t["payments"]) == (
            "Tip: Sample Caterer", tip_cat, caterer, "Sample Caterer", 2000, "following",
            800_000, 160_000, "quote", "On the day", []), t
        t = k[cash_tip]
        assert (t["tip_state"], t["committed_cents"], t["committed_basis"],
                t["tip_basis_points"]) == ("amount", 25_000, "final", None), t
        [cash_pay] = t["payments"]
        assert (cash_pay["amount_cents"], cash_pay["due_on"], cash_pay["paid"],
                cash_pay["payer_id"]) == (25_000, "2027-06-01", False, payer_a), \
            "a due date or payer adds the tip's first payment, unpaid (rule 4)"
        assert k[caterer]["tip_ids"] == [pct_tip, cash_tip] and k[caterer]["tip_state"] is None
        ov = c.get(f"{b_url}/overview", headers=viewer_headers).json()
        assert (ov["dashboard"]["tips_cents"], ov["dashboard"]["tip_count"]) == (185_000, 2)
        cat = next(x for x in ov["categories"] if x["id"] == tip_cat)
        assert cat["committed_cents"] == 800_000 + 185_000, "tips count in the category"
        assert any(d["payment_id"] == cash_pay["id"] and d["vendor_name"] == "Tip: Sample Caterer"
                   for d in ov["next_due"]), "a tip's payment is in Upcoming payments"
        print("   * Add tip: a percentage or an amount, as its own line in the same category, "
              "counted in every total; viewers and outsiders can't")

        assert c.post(f"{b_url}/costs/{pct_tip}/tips", json={"amount_cents": 100},
                      headers=headers).status_code == 422, "a tip can't have a tip"
        res = c.post(f"{b_url}/costs/{no_cost}/tips", json={"percent_basis_points": 1500,
                     "due_on": "2027-06-01"}, headers=headers)
        assert res.status_code == 422 and "no cost yet" in res.json()["detail"], res.text
        res = c.post(f"{b_url}/costs/{no_cost}/tips", json={"percent_basis_points": 1500},
                     headers=headers)
        assert res.status_code == 201
        bar_tip = res.json()["id"]
        t = tip_costs()[bar_tip]
        assert (t["tip_state"], t["committed_cents"], t["committed_basis"]) == (
            "waiting", 0, "none"), "a percentage of no cost waits, counting $0"
        assert c.patch(f"{b_url}/costs/{pct_tip}", json={"quoted_cents": 1},
                       headers=headers).status_code == 422
        assert c.patch(f"{b_url}/costs/{pct_tip}", json={"category_id": pay_cat},
                       headers=headers).status_code in (404, 422)
        assert c.patch(f"{b_url}/tips/{caterer}", json={"amount_cents": 1},
                       headers=headers).status_code == 422, "a plain expense isn't a tip"
        print("   * No tip on a tip; a percentage of no cost waits at $0; a tip's amount "
              "changes only as a tip")

        assert c.patch(f"{b_url}/costs/{caterer}", json={"final_cents": 900_000},
                       headers=headers).status_code == 200
        assert c.patch(f"{b_url}/costs/{no_cost}", json={"estimated_cents": 10_001},
                       headers=headers).status_code == 200
        k = tip_costs()
        assert (k[pct_tip]["committed_cents"], k[pct_tip]["committed_basis"],
                k[pct_tip]["tip_base_cents"]) == (180_000, "final", 900_000), \
            "a percentage tip follows the actual cost"
        assert k[cash_tip]["committed_cents"] == 25_000, "a dollar tip stays as typed"
        assert (k[bar_tip]["tip_state"], k[bar_tip]["committed_cents"]) == ("following", 1500)
        print("   * A percentage tip follows its expense's cost; a dollar tip never moves")

        res = c.post(f"{b_url}/costs/{pct_tip}/payments", json={"amount_cents": 180_000},
                     headers=headers)
        pct_pay = res.json()["id"]
        assert c.put(f"{b_url}/payments/{pct_pay}/paid", json={"paid": True},
                     headers=headers).json()["paid"] is True
        assert c.patch(f"{b_url}/costs/{caterer}", json={"final_cents": 1_000_000},
                       headers=headers).status_code == 200
        t = tip_costs()[pct_tip]
        assert (t["tip_state"], t["committed_cents"], t["status"]) == ("frozen", 180_000, "paid"), \
            "once a payment on it is paid, the tip stays at the amount it was"
        assert c.put(f"{b_url}/payments/{pct_pay}/paid", json={"paid": False},
                     headers=headers).json()["paid"] is False
        t = tip_costs()[pct_tip]
        assert (t["tip_state"], t["committed_cents"], t["final_cents"]) == (
            "following", 200_000, None), "unticked, it follows the cost again"
        assert c.put(f"{b_url}/payments/{pct_pay}/paid", json={"paid": True},
                     headers=headers).status_code == 200
        assert c.delete(f"{b_url}/payments/{pct_pay}", headers=headers).status_code == 204
        assert tip_costs()[pct_tip]["tip_state"] == "following", \
            "removing its only paid payment lets it follow again"
        print("   * Ticking a tip's payment paid fixes its amount; unticking lets it follow again")

        res = c.patch(f"{b_url}/tips/{pct_tip}", json={"amount_cents": 30_000}, headers=headers)
        assert res.status_code == 200 and res.json()["tip_basis_points"] is None
        assert tip_costs()[pct_tip]["committed_cents"] == 30_000
        res = c.patch(f"{b_url}/tips/{pct_tip}", json={"percent_basis_points": 1850,
                      "notes": None}, headers=headers)
        assert res.status_code == 200, res.text
        t = tip_costs()[pct_tip]
        assert (t["tip_state"], t["committed_cents"], t["notes"]) == ("following", 185_000, None)
        assert c.patch(f"{b_url}/tips/{pct_tip}", json={"percent_basis_points": 1000,
                       "amount_cents": 1}, headers=headers).status_code == 422
        assert c.patch(f"{b_url}/tips/{pct_tip}", json={"amount_cents": 1},
                       headers=viewer_headers).status_code == 403
        print("   * Edit tip: switch between a percentage and an amount")

        moved_cat = c.post(f"{b_url}/categories", json={"name": "Placeholder Feast"},
                           headers=headers).json()["id"]
        assert c.patch(f"{b_url}/costs/{caterer}", json={"vendor_name": "Sample Kitchen",
                       "category_id": moved_cat}, headers=headers).status_code == 200
        moved = {x["id"]: x for x in costs_in(moved_cat)}
        assert set(moved) == {caterer, pct_tip, cash_tip}, "tips move with their expense"
        assert moved[pct_tip]["vendor_name"] == "Tip: Sample Kitchen", "and are renamed with it"
        assert c.patch(f"{b_url}/costs/{caterer}", json={"category_id": tip_cat},
                       headers=headers).status_code == 200
        print("   * Moving or renaming an expense takes its tips along")

        got, heads = sections(export())
        assert "Tip for" in heads["Expenses"] and "Tip (%)" in heads["Expenses"]
        [row] = [r for r in got["Expenses"] if r["Tip (%)"] == "18.5"]
        assert (row["Expense"], row["Tip for"], row["Cost (USD)"]) == (
            "Tip: Sample Kitchen", "Sample Kitchen", "1850.00"), row
        assert [r["Tip for"] for r in got["Expenses"] if r["Expense"] == "Sample Kitchen"] == [""]
        summary = {r["Item"]: r["Value"] for r in got["Summary"]}
        assert summary["Tips (USD, already part of committed)"] == "2115.00"
        print("   * Export: each tip says what it's for; the summary gives the tips total")

        before = tip_costs()
        res = c.patch(f"{b_url}/costs/{caterer}", json={"archived": True}, headers=headers)
        assert res.status_code == 409 and "2 tips" in res.json()["detail"], res.text
        assert tip_costs() == before, "asking changes nothing"
        assert c.patch(f"{b_url}/costs/{caterer}?tips=maybe", json={"archived": True},
                       headers=headers).status_code == 422
        assert c.patch(f"{b_url}/costs/{caterer}?tips=remove", json={"archived": True},
                       headers=headers).status_code == 200
        k = tip_costs()
        assert k[caterer]["archived"] and k[pct_tip]["archived"] and k[cash_tip]["archived"]
        assert k[cash_tip]["payments"] == before[cash_tip]["payments"], "archiving keeps payments"
        res = c.patch(f"{b_url}/costs/{pct_tip}", json={"archived": False}, headers=headers)
        assert res.status_code == 422 and "Restore it first" in res.json()["detail"], \
            "a tip isn't counted again while its expense is archived"
        assert c.post(f"{b_url}/costs/{pct_tip}/duplicate",
                      headers=headers).status_code == 422, "nor copied onto it"
        assert c.patch(f"{b_url}/costs/{caterer}", json={"archived": False},
                       headers=headers).status_code == 200
        for tid in (pct_tip, cash_tip):
            assert c.patch(f"{b_url}/costs/{tid}", json={"archived": False},
                           headers=headers).status_code == 200
        res = c.delete(f"{b_url}/costs/{caterer}", headers=headers)
        assert res.status_code == 409 and "remove them too" in res.json()["detail"], res.text
        assert c.delete(f"{b_url}/costs/{caterer}?tips=keep", headers=headers).status_code == 204
        k = tip_costs()
        assert caterer not in k
        for tid, cents in ((pct_tip, 185_000), (cash_tip, 25_000)):
            assert (k[tid]["tip_state"], k[tid]["tip_for_cost_id"], k[tid]["final_cents"],
                    k[tid]["committed_cents"], k[tid]["vendor_name"]) == (
                None, None, cents, cents, "Tip: Sample Kitchen"), k[tid]
        assert k[cash_tip]["payments"] == before[cash_tip]["payments"], "kept with its payment"
        assert c.patch(f"{b_url}/costs/{no_cost}", json={"estimated_cents": None},
                       headers=headers).status_code == 200
        assert tip_costs()[bar_tip]["tip_state"] == "waiting"
        res = c.post(f"{b_url}/costs/{bar_tip}/payments", json={"amount_cents": 1500},
                     headers=headers)
        assert res.status_code == 201
        assert c.put(f"{b_url}/payments/{res.json()['id']}/paid", json={"paid": True},
                     headers=headers).status_code == 200
        assert c.patch(f"{b_url}/costs/{no_cost}", json={"estimated_cents": 100_000},
                       headers=headers).status_code == 200
        t = tip_costs()[bar_tip]
        assert (t["tip_state"], t["committed_cents"]) == ("frozen", 0), \
            "a tip paid while waiting for a cost is fixed (at $0) and doesn't start following"
        assert c.delete(f"{b_url}/costs/{no_cost}?tips=remove",
                        headers=headers).status_code == 204
        assert set(tip_costs()) == {pct_tip, cash_tip}, "removed with its tip"
        with Session(sync_engine) as s:
            assert s.exec(sync_select(BudgetPayment).where(
                BudgetPayment.cost_id == bar_tip)).first() is None, \
                "the tip's payments went with it, as the couple chose"
        ov = c.get(f"{b_url}/overview", headers=headers).json()
        assert (ov["dashboard"]["tips_cents"], ov["dashboard"]["tip_count"]) == (0, 0)
        print("   * Archiving or removing an expense with tips asks: remove them too, or keep "
              "them as plain lines with their dollar figure and payments")

        clear_category(tip_cat)
        clear_category(moved_cat)
        assert c.delete(f"{p_url}/{payer_a}", headers=headers).status_code == 204

        print("7d. Verifying vendor cards compare quotes with the couple's own budget (B42)...")
        from app.db.models import Booking, BudgetLine, Quote, Supplier
        names = {cat["name"].lower() for cat in ours["categories"]}
        assert not names & {"photography", "videography", "cake", "transport"}, names
        assert c.post(f"{b_url}/categories", json={"name": "Photography",
                      "planned_cents": 300_000}, headers=headers).status_code == 201
        assert c.post(f"{b_url}/categories", json={"name": "Videography"},
                      headers=headers).status_code == 201
        assert c.post(f"{b_url}/categories", json={"name": "Transport",
                      "planned_cents": 50_000}, headers=headers).status_code == 201
        # (supplier category, quote total, quote currency)
        cases = {
            "over": ("photography", 3000.01, "USD"),
            "within": ("photography", 3000.00, "usd"),
            "no_category": ("cake", 10.0, "USD"),
            "no_planned_amount": ("videography", 10.0, "USD"),
            "currency_mismatch": ("transport", 900.0, "EUR"),
        }
        with Session(sync_engine) as s:
            # A large old euro row must be ignored: the old over-budget flag came from here.
            s.add(BudgetLine(id="bl_b42_old", wedding_id=wedding_id, category="photography",
                             allocated_amount=99_999.0))
            for key, (cat, total, cur) in cases.items():
                s.add(Supplier(id=f"sup_b42_{key}", name=f"Sample {key}", category=cat,
                               location="Sligo", source="manual"))
                s.add(Booking(id=f"bk_b42_{key}", wedding_id=wedding_id,
                              supplier_id=f"sup_b42_{key}"))
                s.add(Quote(id=f"q_b42_{key}", booking_id=f"bk_b42_{key}",
                            total_amount=total, currency=cur))
            s.commit()
        for who in (headers, viewer_headers):
            res = c.get(f"/api/v1/weddings/{wedding_id}/bookings", headers=who)
            assert res.status_code == 200, res.text
            cards = {b["id"]: b for b in res.json()}
            for key in cases:
                card = cards[f"bk_b42_{key}"]
                assert card["budget_comparison"] == key, (key, card)
                assert card["budget_currency"] == "USD"
            over, within = cards["bk_b42_over"], cards["bk_b42_within"]
            assert (over["over_budget"], over["over_by_cents"], over["planned_cents"]) == (
                True, 1, 300_000), over
            assert over["budget_category_name"] == "Photography"
            assert (within["over_budget"], within["over_by_cents"]) == (False, 0), within
            for key in ("no_category", "no_planned_amount", "currency_mismatch"):
                card = cards[f"bk_b42_{key}"]
                assert card["over_budget"] is None and card["over_by_cents"] is None, card
            assert cards["bk_b42_no_category"]["budget_category_name"] is None
            assert cards["bk_b42_no_category"]["budget_match_key"] == "cake"
            assert "allocated_amount" not in over
        with Session(sync_engine) as s:
            assert s.get(BudgetLine, "bl_b42_old").allocated_amount == 99_999.0
            assert s.get(Booking, "bk_b42_over").status == "shortlisted"
            assert s.get(Quote, "q_b42_over").status == "pending"
        print("   * Vendor cards: over and within against the planned dollars; no flag without a "
              "matching category, a planned amount or a dollar quote; old euro rows ignored")
        from app.utils.budget_compare import to_cents
        assert to_cents(0.1 + 0.2) == 30 and to_cents(1234.565) == 123457
        assert to_cents(float("nan")) is None and to_cents(-1) is None and to_cents(None) is None

        print("7e. Verifying the planning checklist: dates, catch up, overdue, ticks, import (PD-007)...")
        import datetime as dt
        import json as _json
        import tempfile
        from app.api.v1.endpoints import checklist as checklist_module
        from app.db.models import BudgetPayment, ChecklistTask, TimelineItem, User, Wedding
        from app.utils import checklist as rules
        from app.api.v1.endpoints.checklist import IMPORT_BODY_MAX_BYTES
        from app.utils.checklist_import import (
            FILE_MAX_CHARS, ImportRefused, import_checklist, read_owner_list,
        )

        D = dt.date
        # Calendar months keep the day, or use the month's last day.
        assert rules.add_months(D(2027, 8, 31), -6) == D(2027, 2, 28)
        assert rules.add_months(D(2028, 8, 31), -6) == D(2028, 2, 29)
        assert rules.add_months(D(2027, 3, 31), -1) == D(2027, 2, 28)
        assert rules.add_months(D(2027, 1, 31), -12) == D(2026, 1, 31)
        assert rules.add_months(D(2027, 1, 15), -1) == D(2026, 12, 15)
        due = {s.key: rules.stage_due(D(2027, 8, 21), s) for s in rules.STAGES}
        assert (due["12m"], due["9m"], due["1m"]) == (D(2026, 8, 21), D(2026, 11, 21), D(2027, 7, 21))
        assert (due["3w"], due["2-3d"], due["1d"]) == (D(2027, 7, 31), D(2027, 8, 18), D(2027, 8, 20))
        assert (due["day"], due["post"]) == (D(2027, 8, 21), D(2027, 9, 4))
        print("   * Due dates: calendar months (month ends clamp), weeks and days from the wedding date")

        # The PD-007 example: date set on 5 Nov 2026 for 21 Aug 2027.
        plans = rules.plan_groups(D(2027, 8, 21), D(2026, 11, 5), D(2026, 11, 5))
        assert plans[0].kind == "catch_up" and plans[0].stage_keys == ["12m", "11m", "10m"]
        assert plans[0].due_on == D(2026, 11, 21), "catch up is due with 9 Months Before"
        assert [p.key for p in plans[1:3]] == ["9m", "8m"] and not any(p.past for p in plans)
        # Seven weeks later, 9m and 8m have passed since the date was set: overdue, while
        # the stages already past when it was set stay "catch up".
        later = rules.plan_groups(D(2027, 8, 21), D(2026, 11, 5), D(2026, 12, 25))
        assert later[0].stage_keys == ["12m", "11m", "10m"]
        assert [p.key for p in later if p.past] == ["9m", "8m"]
        assert rules.task_label(later[0], False) == "catch_up"
        assert rules.task_label(later[1], False) == "overdue"
        assert rules.task_label(later[1], True) is None
        assert rules.plan_groups(None, None, D(2026, 11, 5))[0].due_on is None
        assert rules.title_key("  Book the  VENUE. ") == rules.title_key("book the venue")
        print("   * Catch up vs overdue: past-when-set stages are 'catch up', later ones 'overdue'")

        cl_url = f"/api/v1/weddings/{wedding_id}/checklist"
        real_today = checklist_module._today
        checklist_module._today = lambda: D(2026, 11, 5)
        try:
            res = c.get(cl_url, headers=viewer_headers)
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["wedding_date"] is None and body["total"] == 0
            assert len(body["groups"]) == 19 and all(g["due_on"] is None for g in body["groups"])
            assert c.get(cl_url, headers=unauth_headers).status_code == 403

            with Session(sync_engine) as s:
                status_before = s.get(Wedding, wedding_id).status
            assert c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"},
                         headers=viewer_headers).status_code == 403
            assert c.put(f"{cl_url}/date", json={"wedding_date": "2026-11-04"},
                         headers=editor_headers).status_code == 422
            res = c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"}, headers=editor_headers)
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["date_set_on"] == "2026-11-05"
            g0 = body["groups"][0]
            assert (g0["key"], g0["label"], g0["due_on"]) == ("catch_up", "Catch up", "2026-11-21")
            assert g0["add_to_stage"] == "10m" and body["groups"][1]["key"] == "9m"
            with Session(sync_engine) as s:
                assert s.get(Wedding, wedding_id).status == status_before, "date keeps the plan"
            print("   * Date: set by an editor (never by viewers or to a past day); catch up formed")

            add = lambda stage, title, who=editor_headers: c.post(
                f"{cl_url}/tasks", json={"stage": stage, "title": title}, headers=who)
            assert add("9m", "Placeholder task", viewer_headers).status_code == 403
            assert add("13m", "Placeholder task").status_code == 422
            assert add("9m", "   ").status_code == 422
            t_catch = add("11m", "  Placeholder  early task ").json()
            assert t_catch["title"] == "Placeholder early task" and t_catch["label"] == "catch_up"
            t_now = add("9m", "Placeholder current task").json()
            t_soon = add("8m", "Placeholder next task").json()
            t_late = add("1m", "Placeholder later task").json()
            assert t_now["label"] is None and t_now["position"] == 1
            assert add("9m", "Placeholder second current task").json()["position"] == 2

            with Session(sync_engine) as s:
                paid_before = [(p.id, p.paid) for p in s.exec(sync_select(BudgetPayment)).all()]
            done_url = f"{cl_url}/tasks/{t_now['id']}/done"
            assert c.put(done_url, json={"done": True}, headers=viewer_headers).status_code == 403
            res = c.put(done_url, json={"done": True}, headers=editor_headers)
            assert res.status_code == 200 and res.json()["done"] is True, res.text
            first_done_at = res.json()["done_at"]
            assert first_done_at and res.json()["done_by_name"]
            # Ticking again keeps the first record; the owner sees the editor's tick.
            assert c.put(done_url, json={"done": True}, headers=headers).json()["done_at"] == first_done_at
            body = c.get(cl_url, headers=headers).json()
            assert (body["done"], body["total"]) == (1, 5)
            nine = next(g for g in body["groups"] if g["key"] == "9m")
            assert (nine["done"], nine["total"], nine["current"]) == (1, 2, True)
            assert body["groups"][0]["current"] is True, "catch up opens while it has tasks left"
            assert next(g for g in body["groups"] if g["key"] == "8m")["current"] is False
            res = c.put(done_url, json={"done": False}, headers=editor_headers).json()
            assert (res["done"], res["done_at"], res["done_by_name"]) == (False, None, None)
            c.put(done_url, json={"done": True}, headers=editor_headers)
            with Session(sync_engine) as s:
                assert [(p.id, p.paid) for p in s.exec(sync_select(BudgetPayment)).all()] == paid_before
            print("   * Ticks: shared, record who and when, untick clears; payments untouched")

            t_url = f"{cl_url}/tasks/{t_soon['id']}"
            assert c.patch(t_url, json={"title": "Renamed"}, headers=viewer_headers).status_code == 403
            res = c.patch(t_url, json={"title": " Renamed  placeholder ", "notes": "A note"},
                          headers=editor_headers)
            assert res.json()["title"] == "Renamed placeholder" and res.json()["notes"] == "A note"
            assert c.patch(t_url, json={"title": ""}, headers=editor_headers).status_code == 422
            assert c.delete(t_url, headers=viewer_headers).status_code == 403
            assert c.delete(t_url, headers=editor_headers).status_code == 204
            assert c.delete(t_url, headers=editor_headers).status_code == 404
            print("   * Edit: editors rename, note and delete; viewers can't")

            # Seven weeks on, 9m's unfinished task is overdue; catch up stays catch up.
            checklist_module._today = lambda: D(2026, 12, 25)
            body = c.get(cl_url, headers=viewer_headers).json()
            labels = {t["title"]: t["label"] for g in body["groups"] for t in g["tasks"]}
            assert labels["Placeholder early task"] == "catch_up"
            assert labels["Placeholder second current task"] == "overdue"
            assert labels["Placeholder current task"] is None, "done tasks are never overdue"
            assert labels["Placeholder later task"] is None and body["overdue"] == 1
            assert next(g for g in body["groups"] if g["current"] and g["kind"] == "stage")["key"] == "7m"

            # Moving the date recomputes everything from the new "set on" day.
            res = c.put(f"{cl_url}/date", json={"wedding_date": "2028-08-21"},
                        headers=editor_headers).json()
            assert res["groups"][0]["key"] == "12m", "nothing is past for a 2028 date"
            assert res["overdue"] == 0
            res = c.put(f"{cl_url}/date", json={"wedding_date": None}, headers=editor_headers).json()
            assert res["wedding_date"] is None and res["date_set_on"] is None and res["overdue"] == 0
            assert res["done"] == 1 and res["total"] == 4, "clearing the date keeps every task"
            c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"}, headers=editor_headers)
            # "Today" pinned, so a run across midnight in Chicago can't fail falsely (B45).
            real_wedding_today = rules.wedding_today
            rules.wedding_today = lambda: D(2026, 11, 6)
            try:
                assert c.patch(f"/api/v1/weddings/{wedding_id}",
                               json={"wedding_date": "2027-09-04"},
                               headers=editor_headers).status_code == 200
            finally:
                rules.wedding_today = real_wedding_today
            with Session(sync_engine) as s:
                assert s.get(Wedding, wedding_id).wedding_date_set_on == D(2026, 11, 6)
            assert c.patch(f"/api/v1/weddings/{wedding_id}", json={"wedding_date": "2020-01-01"},
                           headers=editor_headers).status_code == 422, "same rule as the checklist"
            with Session(sync_engine) as s:
                assert s.get(Wedding, wedding_id).wedding_date == D(2027, 9, 4)
            c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"}, headers=editor_headers)
            print("   * Date changes: groups and labels recompute; clearing the date keeps tasks")

            # B48: "This date is confirmed" is off until the couple switch it on.
            conf_url = f"{cl_url}/date-confirmed"
            assert c.get(cl_url, headers=viewer_headers).json()["date_confirmed"] is False
            assert c.put(conf_url, json={"confirmed": True},
                         headers=viewer_headers).status_code == 403, "viewers can't switch it"
            assert c.put(conf_url, json={"confirmed": True},
                         headers=unauth_headers).status_code == 403
            assert c.put(conf_url, json={}, headers=editor_headers).status_code == 422
            res = c.put(conf_url, json={"confirmed": True}, headers=editor_headers)
            assert res.status_code == 200 and res.json()["date_confirmed"] is True, res.text
            assert c.get(cl_url, headers=viewer_headers).json()["date_confirmed"] is True
            # Changing the date, either way, leaves the switch as the couple set it.
            assert c.put(f"{cl_url}/date", json={"wedding_date": "2027-09-11"},
                         headers=editor_headers).json()["date_confirmed"] is True
            assert c.patch(f"/api/v1/weddings/{wedding_id}", json={"wedding_date": "2027-08-21"},
                           headers=editor_headers).json()["wedding_date_confirmed"] is True
            assert c.patch(f"/api/v1/weddings/{wedding_id}",
                           json={"wedding_date_confirmed": False},
                           headers=editor_headers).json()["wedding_date_confirmed"] is True, \
                "only the switch's own route changes it"
            res = c.put(conf_url, json={"confirmed": False}, headers=headers)
            assert res.status_code == 200 and res.json()["date_confirmed"] is False, res.text
            c.put(f"{cl_url}/date", json={"wedding_date": None}, headers=editor_headers)
            assert c.put(conf_url, json={"confirmed": True},
                         headers=editor_headers).status_code == 422, "no date, nothing to confirm"
            c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"}, headers=editor_headers)
            print("   * Confirmed switch: owners and editors only; date changes leave it alone")
        finally:
            checklist_module._today = real_today

        # The import, with fictional placeholder tasks only.
        tmp = tempfile.mkdtemp()
        stages = []
        for st in rules.STAGES:
            offset = {k: v for k, v in (("months", st.months), ("weeks", st.weeks),
                                        ("days", st.days)) if v} or {"days": 0}
            items = [f"Placeholder {st.key} task {n}" for n in (1, 2, 3)]
            if st.key == "11m":
                items[2] = "Placeholder: find someone to officiate"
            stages.append({"id": st.key, "label": st.label, "offset": offset, "items": items})
        owner_file = os.path.join(tmp, "owner-list.md")
        with open(owner_file, "w") as f:
            f.write("Notes first\n\n```json\n" + _json.dumps(stages) + "\n```\n")
        owner_list = read_owner_list(owner_file)

        with Session(sync_engine) as s:
            s.add(User(id="u_import", role="couple", name="Import Test", email="imp@example.test"))
            s.add(Wedding(id="w_import", couple_user_id="u_import", region="Sligo",
                          ceremony_type="Civil", guest_count_estimate=10, budget_total=1.0))
            s.flush()
            s.add(TimelineItem(id="ti_imp_dup", wedding_id="w_import", kind="planning",
                               title="  PLACEHOLDER 9m   task 1. ", due_at=D(2026, 11, 20),
                               description="Fictional AI note", status="done"))
            s.add(TimelineItem(id="ti_imp_new", wedding_id="w_import", kind="planning",
                               title="Fictional AI task", description="From the planner",
                               due_at=D(2027, 2, 20), status="done"))
            s.add(TimelineItem(id="ti_imp_day", wedding_id="w_import", kind="day_of",
                               title="Fictional rehearsal", due_at=D(2027, 8, 19)))
            s.commit()

        with Session(sync_engine) as s:
            w = s.get(Wedding, "w_import")
            bad = [dict(x) for x in stages]
            bad[1] = dict(bad[1], items=["Placeholder a", "Placeholder b", "Not about that"])
            try:
                import_checklist(s, w, bad, D(2027, 8, 21), today=D(2026, 11, 5))
                raise AssertionError("an unexpected 11m-3 should refuse the import")
            except ImportRefused:
                s.rollback()
            w = s.get(Wedding, "w_import")
            try:
                import_checklist(s, w, owner_list, None, today=D(2026, 11, 5))
                raise AssertionError("merging the timeline needs a wedding date")
            except ImportRefused:
                s.rollback()
        with Session(sync_engine) as s:
            assert s.exec(sync_select(ChecklistTask).where(
                ChecklistTask.wedding_id == "w_import")).all() == [], "refusals write nothing"
            assert len(s.exec(sync_select(TimelineItem).where(
                TimelineItem.wedding_id == "w_import")).all()) == 3
        for wrong in ([{"id": "x"}], [dict(stages[0], offset={"months": -11})] + stages[1:]):
            with open(os.path.join(tmp, "bad.json"), "w") as f:
                f.write(_json.dumps(wrong))
            try:
                read_owner_list(os.path.join(tmp, "bad.json"))
                raise AssertionError("a file with other stages should be refused")
            except ImportRefused:
                pass

        # A dry run (rolled back) changes nothing; then the real run.
        with Session(sync_engine) as s:
            import_checklist(s, s.get(Wedding, "w_import"), owner_list, D(2027, 8, 21),
                             today=D(2026, 11, 5))
            s.rollback()
        with Session(sync_engine) as s:
            assert s.get(Wedding, "w_import").wedding_date is None
            assert len(s.exec(sync_select(TimelineItem).where(
                TimelineItem.wedding_id == "w_import")).all()) == 3
            report = import_checklist(s, s.get(Wedding, "w_import"), owner_list, D(2027, 8, 21),
                                      today=D(2026, 11, 5))
            s.commit()
        assert (report.owner_tasks, report.tradition_tasks, report.venue_tasks) == (
            19 * 3 - 1, 18, 3), report
        assert report.ai_added == ["Fictional AI task -> 6 Months Before",
                                   "Fictional rehearsal -> 2–3 Days Before"], report.ai_added
        assert report.ai_skipped == [
            "PLACEHOLDER 9m task 1. = Placeholder 9m task 1 (ticked, notes copied)"], report.ai_skipped
        assert report.timeline_rows_removed == 3
        with Session(sync_engine) as s:
            w = s.get(Wedding, "w_import")
            assert (w.wedding_date, w.wedding_date_set_on) == (D(2027, 8, 21), D(2026, 11, 5))
            assert w.checklist_imported_at is not None
            assert s.exec(sync_select(TimelineItem).where(
                TimelineItem.wedding_id == "w_import")).all() == []
            tasks = s.exec(sync_select(ChecklistTask).where(
                ChecklistTask.wedding_id == "w_import")).all()
            # 56 placeholder tasks, 18 traditions, the 3 Wildman BT tasks, 2 AI tasks.
            assert len(tasks) == 56 + 18 + 3 + 2
            venue = {t.source_ref: t for t in tasks if t.source_ref in ("V1", "V2", "V3")}
            assert {r: (t.stage, t.source, t.done) for r, t in venue.items()} == {
                "V1": ("12m", "owner_list", False), "V2": ("1m", "owner_list", False),
                "V3": ("post", "owner_list", False)}, "in their stages, none ticked"
            assert "Due Wed 11 Nov 2026" in venue["V1"].title
            assert "Due Thu 23 Sep 2027" in venue["V2"].title
            assert "22 Nov 2027" in venue["V3"].title
            eleven = sorted((t for t in tasks if t.stage == "11m"), key=lambda t: t.position)
            assert [t.source_ref for t in eleven] == ["11m-1", "11m-2", "J2"]
            assert "officiat" not in " ".join(t.title for t in eleven).lower()
            dup = next(t for t in tasks if t.source_ref == "9m-1")
            assert dup.done and dup.notes == "Fictional AI note", "a duplicate keeps its tick"
            assert dup.done_at is None, "the timeline never said when; nothing is guessed"
            ai = {t.source_ref: t for t in tasks if t.source == "ai_timeline"}
            assert ai["ti:ti_imp_new"].done and ai["ti:ti_imp_new"].notes == "From the planner"
            their_task = ai["ti:ti_imp_new"].id
            assert {t.source_ref for t in tasks if t.source == "tradition"} == {
                ref for ref, _, _ in rules.TRADITIONS}
            again_refused = False
            try:
                import_checklist(s, w, owner_list, None, today=D(2026, 11, 5))
            except ImportRefused:
                again_refused = True
            s.rollback()
            assert again_refused, "the import runs once"
        for method, url in (("put", f"{cl_url}/tasks/{their_task}/done"),
                            ("patch", f"{cl_url}/tasks/{their_task}"),
                            ("delete", f"{cl_url}/tasks/{their_task}")):
            kwargs = {} if method == "delete" else {
                "json": {"done": False} if method == "put" else {"title": "x"}}
            assert getattr(c, method)(url, headers=headers, **kwargs).status_code == 404
        with Session(sync_engine) as s:
            assert s.get(ChecklistTask, their_task).done is True, "untouched"
        print("   * Cross-wedding: another wedding's tasks are refused (404) and untouched")

        # A wedding that already had the date (made at intake before "set on" existed),
        # imported with the same date: the import records the day, so stages that pass
        # afterwards are overdue and "Catch up" doesn't grow.
        from app.utils.checklist_import import _check_timeline_accounted_for
        with Session(sync_engine) as s:
            s.add(Wedding(id="w_import2", couple_user_id="u_import", region="Sligo",
                          ceremony_type="Civil", guest_count_estimate=10, budget_total=1.0,
                          wedding_date=D(2027, 8, 21)))
            s.flush()
            s.add(TimelineItem(id="ti_imp2", wedding_id="w_import2", kind="planning",
                               title="Fictional second AI task", due_at=D(2027, 1, 21)))
            s.commit()
        with Session(sync_engine) as s:
            timeline2 = s.exec(sync_select(TimelineItem).where(
                TimelineItem.wedding_id == "w_import2")).all()
            try:
                _check_timeline_accounted_for(s, "w_import2", timeline2)
                raise AssertionError("rows not on the checklist must stop the delete")
            except ImportRefused:
                pass
            import_checklist(s, s.get(Wedding, "w_import2"), owner_list, D(2027, 8, 21),
                             today=D(2026, 11, 5))
            s.commit()
        with Session(sync_engine) as s:
            w2 = s.get(Wedding, "w_import2")
            assert w2.wedding_date_set_on == D(2026, 11, 5)
            later = rules.plan_groups(w2.wedding_date, w2.wedding_date_set_on, D(2026, 12, 25))
            assert later[0].stage_keys == ["12m", "11m", "10m"], "catch up doesn't grow"
            assert [p.key for p in later if p.past] == ["9m", "8m"], "passed since: overdue"
            assert s.get(TimelineItem, "ti_imp2") is None
        print("   * Import with the date already set records the day, so later stages go overdue; "
              "the pre-delete check refuses rows that aren't on the checklist")
        print("   * Import: owner's list (11m-3 replaced by J2), 18 traditions, AI timeline merged "
              "by nearest stage with duplicates skipped, timeline removed; runs once; refusals "
              "and dry runs write nothing")

        # "Load my checklist" from the Checklist screen (PD-011): same import, same refusals.
        imp_url = f"{cl_url}/import"
        with open(owner_file) as f:
            owner_text = f.read()
        load = lambda body, who=editor_headers: c.post(imp_url, json=body, headers=who)
        with Session(sync_engine) as s:
            paid_before = [(p.id, p.paid) for p in s.exec(sync_select(BudgetPayment)).all()]
            tasks_before = len(s.exec(sync_select(ChecklistTask).where(
                ChecklistTask.wedding_id == wedding_id)).all())
        # Two fictional AI timeline rows: one matching the couple's own task, one new.
        with Session(sync_engine) as s:
            later_task = s.exec(sync_select(ChecklistTask).where(
                ChecklistTask.wedding_id == wedding_id,
                ChecklistTask.title == "Placeholder later task")).one()
            later_id = later_task.id
            assert (later_task.done, later_task.notes) == (False, None)
            s.add(TimelineItem(id="ti_load_dup", wedding_id=wedding_id, kind="planning",
                               title="placeholder LATER task", due_at=D(2027, 7, 1),
                               description="Fictional load note", status="done"))
            s.add(TimelineItem(id="ti_load_new", wedding_id=wedding_id, kind="planning",
                               title="Fictional load AI task", due_at=D(2027, 3, 1)))
            s.commit()
        checklist_module._today = lambda: D(2026, 11, 5)
        try:
            assert c.get(cl_url, headers=viewer_headers).json()["imported"] is False
            ok_body = {"text": owner_text, "apply": True}
            assert load(ok_body, viewer_headers).status_code == 403, "viewers can't load"
            assert load(ok_body, unauth_headers).status_code == 403
            assert c.post(imp_url, content=b"not json", headers=editor_headers).status_code == 422
            assert load({"text": owner_text}).status_code == 422, "save flag required"
            assert load({"text": 5, "apply": False}).status_code == 422
            assert load({"text": "x" * (FILE_MAX_CHARS + 1), "apply": True}).status_code == 422
            assert c.post(imp_url, content=b"x" * (IMPORT_BODY_MAX_BYTES + 1),
                          headers=editor_headers).status_code == 413
            assert load({"text": _json.dumps(stages[1:]), "apply": True}).status_code == 422
            swapped = [stages[1], stages[0]] + stages[2:]
            assert load({"text": _json.dumps(swapped), "apply": True}).status_code == 422
            marker = "Placeholder unique marker " + "z" * 300
            too_long = [dict(stages[0], items=[marker])] + stages[1:]
            res = load({"text": _json.dumps(too_long), "apply": True})
            assert res.status_code == 422 and "unique marker" not in res.text, res.text
            assert "over 300 characters" in res.json()["detail"]
            named = [dict(stages[0], id="Fictional Guest Name")] + stages[1:]
            res = load({"text": _json.dumps(named), "apply": False})
            assert res.status_code == 422 and "Fictional Guest" not in res.text, res.text
            res = load({"text": "```json\n" + "\n" * 150_000, "apply": False})
            assert res.status_code == 422, "an unclosed fence is refused quickly"
            assert load({"text": "[" * 100_000, "apply": False}).status_code == 422
            assert c.post(imp_url, content=b"[" * 100_000,
                          headers=editor_headers).status_code == 422
            # The AI timeline needs a date to place its rows: refused without one.
            c.put(f"{cl_url}/date", json={"wedding_date": None}, headers=editor_headers)
            res = load({"text": owner_text, "apply": False})
            assert res.status_code == 422 and "wedding date" in res.json()["detail"], res.text
            c.put(f"{cl_url}/date", json={"wedding_date": "2027-08-21"}, headers=editor_headers)

            # The practice run saves nothing; owners can run it as well as editors.
            res = load({"text": owner_text, "apply": False}, headers)
            assert res.status_code == 200, res.text
            practice = res.json()
            assert practice["saved"] is False
            assert (practice["owner_tasks"], practice["tradition_tasks"],
                    practice["venue_tasks"]) == (56, 18, 3), practice
            assert practice["wedding_date"] == "2027-08-21"
            assert (practice["ai_added"], practice["ai_skipped"],
                    practice["timeline_rows_removed"]) == (1, 1, 2), practice
            assert "Placeholder" not in res.text, "counts only, never the file's wording"
            body = c.get(cl_url, headers=viewer_headers).json()
            assert body["imported"] is False and body["total"] == tasks_before
            with Session(sync_engine) as s:
                assert s.get(TimelineItem, "ti_load_dup") is not None
                assert s.get(TimelineItem, "ti_load_new") is not None
                unchanged = s.get(ChecklistTask, later_id)
                assert (unchanged.done, unchanged.notes) == (False, None), "no merge saved"

            res = load({"text": owner_text, "apply": True})
            assert res.status_code == 200, res.text
            saved = res.json()
            assert saved["saved"] is True and {k: v for k, v in saved.items() if k != "saved"} \
                == {k: v for k, v in practice.items() if k != "saved"}, "same as the practice"
            body = c.get(cl_url, headers=viewer_headers).json()
            assert body["imported"] is True
            assert body["total"] == tasks_before + 56 + 18 + 3 + saved["ai_added"]
            again = load({"text": owner_text, "apply": False})
            assert again.status_code == 409, "runs once, even as a practice run"
            with Session(sync_engine) as s:
                assert s.get(TimelineItem, "ti_load_dup") is None
                assert s.get(TimelineItem, "ti_load_new") is None
                merged = s.get(ChecklistTask, later_id)
                assert (merged.done, merged.notes) == (True, "Fictional load note")
        finally:
            checklist_module._today = real_today
        with Session(sync_engine) as s:
            assert [(p.id, p.paid) for p in s.exec(sync_select(BudgetPayment)).all()] == paid_before
            rows = s.exec(sync_select(ChecklistTask).where(
                ChecklistTask.wedding_id == wedding_id,
                ChecklistTask.source_ref.in_(["V1", "V2", "V3"]))).all()
            assert sorted((t.source_ref, t.stage, t.done) for t in rows) == [
                ("V1", "12m", False), ("V2", "1m", False), ("V3", "post", False)]
        print("   * Load my checklist: owners and editors only; refuses wrong, reordered or "
              "over-long files and oversized uploads without echoing them; the practice run "
              "saves nothing; the save adds the list, traditions and Wildman BT tasks once; "
              "nothing marked paid")

        print("7f. Verifying the couple's own vendors (PD-012, B62)...")
        from app.api.v1.endpoints import vendors as vendors_module
        from app.db.models import CoupleVendor, CoupleVendorQuote

        v_url = f"/api/v1/weddings/{wedding_id}/vendors"
        res = c.get(v_url, headers=viewer_headers)
        assert res.status_code == 200, res.text
        assert res.json()["sections"] == [
            "venue", "food_drink", "flowers_decoration", "photo_video", "entertainment",
            "hair_makeup", "transportation"], "the seven sections, in PD-012's order"
        assert res.json()["vendors"] == []
        assert c.get(v_url, headers=unauth_headers).status_code == 403

        florist = {"section": "flowers_decoration", "name": "  Placeholder   Florals ",
                   "website": "https://florist.example.test/", "contact_name": "Test Contact",
                   "email": "hello@florist.example.test", "phone": "+1 (555) 010-0000 ext 2",
                   "notes": "Fictional."}
        assert c.post(v_url, json=florist, headers=viewer_headers).status_code == 403, \
            "viewers can't add"
        res = c.post(v_url, json=florist, headers=editor_headers)
        assert res.status_code == 201, res.text
        vendor = res.json()
        assert vendor["name"] == "Placeholder Florals", "spacing is tidied"
        assert vendor["status"] == "looking", "a new vendor starts as looking"
        assert vendor["latest_reply"] is None
        vid = vendor["id"]
        res = c.post(v_url, json={"section": "venue", "name": "Fictional Hall"}, headers=headers)
        assert res.status_code == 201 and res.json()["website"] is None, "owners add too"
        hall_id = res.json()["id"]

        for bad in ({"name": "   "}, {"section": "catering"}, {"status": "paid"},
                    {"website": "javascript:alert(1)"}, {"website": "ftp://x.example.test"},
                    {"website": "florist.example.test"}, {"website": "https://"},
                    {"website": "https://exa mple.test"}, {"email": "not-an-email"},
                    {"email": "a@b"}, {"email": "a b@example.test"},
                    {"email": "a@b.example.test?subject=x&body=y"},
                    {"website": "https://www.example.test@other.example.test/"}, {"phone": "call me"},
                    {"phone": "12"}, {"name": "x" * 201}, {"notes": "x" * 2001}):
            res = c.post(v_url, json=dict(florist, **bad), headers=editor_headers)
            assert res.status_code == 422, (bad, res.status_code)
        res = c.post(v_url, json={"section": "photo_video", "name": "P", "website": "  ",
                                  "email": "", "phone": " "}, headers=editor_headers)
        assert res.status_code == 201 and (res.json()["website"], res.json()["email"],
                                           res.json()["phone"]) == (None, None, None)
        blank_id = res.json()["id"]
        print("   * Add: owners and editors only; name required; http/https sites, emails "
              "and phones checked; blanks saved as empty; status starts as looking")

        res = c.patch(f"{v_url}/{vid}", json={"status": "booked"}, headers=viewer_headers)
        assert res.status_code == 403, "viewers can't change the status"
        res = c.patch(f"{v_url}/{vid}", json={"status": "contacted", "phone": None,
                                              "notes": "  Called back.  "},
                      headers=editor_headers)
        assert res.status_code == 200, res.text
        assert (res.json()["status"], res.json()["phone"], res.json()["notes"],
                res.json()["email"]) == ("contacted", None, "Called back.",
                                         "hello@florist.example.test"), res.json()
        for bad in ({"name": None}, {"status": None}, {"section": None}, {"status": "paid"},
                    {"website": "data:text/html,x"}):
            assert c.patch(f"{v_url}/{vid}", json=bad, headers=editor_headers).status_code \
                == 422, bad
        assert c.patch(f"/api/v1/weddings/wedding_planning_test/vendors/{vid}",
                       json={"name": "X"}, headers={"Authorization": "Bearer mock-couple_2"}
                       ).status_code == 404, "a vendor is only reachable through its wedding"
        print("   * Edit: only the fields sent change; status only from the couple's choice")

        # Paste a reply: the cleaned text first, nothing sent; then the approved text goes.
        reply = {"email_body": "Hi, thanks! Our package is $2,400 total. "
                               "Test Contact, hello@florist.example.test, 555 010 0000"}
        queued.clear()
        real_vendor_enqueue = vendors_module.enqueue_agent_task
        vendors_module.enqueue_agent_task = _record
        try:
            assert c.post(f"{v_url}/{vid}/reply", json=reply,
                          headers=viewer_headers).status_code == 403
            res = c.post(f"{v_url}/{vid}/reply", json=reply, headers=editor_headers)
            body = res.json()
            assert body["needs_review"] is True and queued == [], res.text
            assert "$2,400 total" in body["preview"]
            for detail in ("Test Contact", "hello@florist", "555 010 0000"):
                assert detail not in body["preview"], f"vendor contact sent to the AI: {detail}"
            res = c.post(f"{v_url}/{vid}/reply", headers=editor_headers,
                         json=dict(reply, approved_prompt=body["preview"]))
            assert res.status_code == 202, res.text
            assert queued == [("vendor-reply", {
                "wedding_id": wedding_id, "vendor_id": vid, "email_body": reply["email_body"],
                "approved_prompt": body["preview"]})], queued
            assert c.post(f"{v_url}/missing/reply", json=reply,
                          headers=editor_headers).status_code == 404
            assert c.post(f"{v_url}/{vid}/reply", json={"email_body": ""},
                          headers=editor_headers).status_code == 422
        finally:
            vendors_module.enqueue_agent_task = real_vendor_enqueue
        print("   * Paste a reply: editors only; the cleaned text first, without the "
              "vendor's contact details; sent only with the approved text")

        # The latest AI reading shows on the card; the status stays the couple's.
        with Session(sync_engine) as s:
            s.add(CoupleVendorQuote(vendor_id=vid, total_cents=240000, currency="USD",
                                    is_available=True, summary="Fictional reading.",
                                    line_items=[{"item": "Package", "amount_cents": 240000}]))
            s.commit()
        res = c.get(v_url, headers=viewer_headers)
        listed = {v["id"]: v for v in res.json()["vendors"]}
        assert listed[vid]["latest_reply"]["total_cents"] == 240000
        assert listed[vid]["status"] == "contacted"
        assert listed[vid]["contact_name"] == "Test Contact", "viewers see the details"

        # Not selected (PD-012 follow-up 2): set only by owners and editors, and ignored
        # by the section's status, so a section of ruled-out vendors is still to do.
        assert res.json()["section_status"] == {
            "venue": "looking", "food_drink": "todo", "flowers_decoration": "contacted",
            "photo_video": "looking", "entertainment": "todo", "hair_makeup": "todo",
            "transportation": "todo"}, res.json()["section_status"]
        assert c.patch(f"{v_url}/{hall_id}", json={"status": "not_selected"},
                       headers=viewer_headers).status_code == 403, "viewers can't rule one out"
        assert c.patch(f"{v_url}/{hall_id}", json={"status": "contacted"},
                       headers=editor_headers).status_code == 200
        res = c.patch(f"{v_url}/{hall_id}", json={"status": "not_selected"},
                      headers=editor_headers)
        assert res.status_code == 200 and res.json()["status"] == "not_selected", res.text
        with Session(sync_engine) as s:
            hall_row = s.get(CoupleVendor, hall_id)
            assert (hall_row.status, hall_row.not_selected) == ("contacted", True)
        res = c.post(v_url, json={"section": "venue", "name": "Fictional Barn",
                                  "status": "not_selected"}, headers=viewer_headers)
        assert res.status_code == 403, "viewers can't add one ruled out either"
        res = c.post(v_url, json={"section": "venue", "name": "Fictional Barn",
                                  "status": "not_selected"}, headers=headers)
        assert res.status_code == 201 and res.json()["status"] == "not_selected", res.text
        barn_id = res.json()["id"]
        body = c.get(v_url, headers=viewer_headers).json()
        assert body["section_status"]["venue"] == "todo", "all ruled out: still to do"
        assert {v["id"]: v["status"] for v in body["vendors"]}[hall_id] == "not_selected"
        res = c.post(v_url, json={"section": "venue", "name": "Fictional Manor",
                                  "status": "booked"}, headers=editor_headers)
        manor_id = res.json()["id"]
        assert c.get(v_url, headers=viewer_headers).json()["section_status"]["venue"] \
            == "booked", "a vendor still in play sets the section's status"
        assert c.delete(f"{v_url}/{manor_id}", headers=editor_headers).status_code == 204
        res = c.patch(f"{v_url}/{hall_id}", json={"status": "looking"}, headers=editor_headers)
        assert res.json()["status"] == "looking", "choosing another status brings it back"
        with Session(sync_engine) as s:
            assert s.get(CoupleVendor, hall_id).not_selected is False
        assert c.get(v_url, headers=viewer_headers).json()["section_status"]["venue"] \
            == "looking"
        assert (vendors_module.section_status([]), vendors_module.section_status(
            ["not_selected", "looking", "not_selected"])) == ("todo", "looking")
        assert c.delete(f"{v_url}/{barn_id}", headers=editor_headers).status_code == 204
        print("   * Not selected: owners and editors only; ignored by the section's status, "
              "so a section of ruled-out vendors shows still to do")

        assert c.delete(f"{v_url}/{vid}", headers=viewer_headers).status_code == 403
        assert c.delete(f"{v_url}/{vid}", headers=editor_headers).status_code == 204
        assert c.delete(f"{v_url}/{vid}", headers=editor_headers).status_code == 404
        for other in (hall_id, blank_id):
            assert c.delete(f"{v_url}/{other}", headers=headers).status_code == 204
        with Session(sync_engine) as s:
            assert s.exec(sync_select(CoupleVendorQuote).where(
                CoupleVendorQuote.vendor_id == vid)).all() == [], "its readings go with it"
            assert s.exec(sync_select(CoupleVendor).where(
                CoupleVendor.wedding_id == wedding_id)).all() == []
        print("   * Remove: owners and editors only; the vendor's AI readings go with it")

        forged = pyjwt.encode({"sub": "forged_admin", "role": "admin"},
                              "dev-jwt-secret-key-change-me-in-production", algorithm="HS256")
        res = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert res.status_code == 401
        print("   * Sign-in: token signed with the old default secret is rejected")

        settings.ALLOW_MOCK_AUTH = False
        try:
            assert c.get("/api/v1/auth/me", headers=viewer_headers).status_code == 401
        finally:
            settings.ALLOW_MOCK_AUTH = True
        print("   * Sign-in: mock tokens are off when mock sign-in is off")

        import asyncio
        from app.db.session import async_session_maker
        from app.api.v1.endpoints.auth import _email_is_allowed
        from app.api.v1.access import link_memberships
        from app.db.models import User as UserModel

        async def _signup_rules():
            async with async_session_maker() as db:
                assert not await _email_is_allowed(db, "stranger@example.test")
                assert await _email_is_allowed(db, "viewer_1@example.test")
                settings.ACCESS_BOOTSTRAP_EMAILS = "First@Example.test"
                try:
                    assert await _email_is_allowed(db, "first@example.test")
                finally:
                    settings.ACCESS_BOOTSTRAP_EMAILS = ""
                with Session(sync_engine) as s:
                    s.add(UserModel(id="new_member", role="couple", name="n", email="pending@example.test"))
                    s.add(WeddingMember(wedding_id=wedding_id, email="pending@example.test", level="viewer"))
                    s.commit()
                user = await db.get(UserModel, "new_member")
                assert await link_memberships(db, user, "Pending@Example.test")
                await db.commit()
            with Session(sync_engine) as s:
                row = s.exec(sync_select(WeddingMember).where(
                    WeddingMember.email == "pending@example.test")).one()
                assert row.user_id == "new_member"
                # Same person, new address also listed: they keep one row, not two levels.
                s.add(WeddingMember(wedding_id=wedding_id, email="pending.new@example.test", level="owner"))
                s.commit()
            async with async_session_maker() as db:
                user = await db.get(UserModel, "new_member")
                assert await link_memberships(db, user, "pending.new@example.test")
                await db.commit()
            with Session(sync_engine) as s:
                row = s.exec(sync_select(WeddingMember).where(
                    WeddingMember.email == "pending.new@example.test")).one()
                assert row.user_id is None
                s.delete(row)
                s.commit()

        asyncio.run(_signup_rules())
        print("   * Sign-up: only listed or bootstrap emails may create an account; list rows link on sign-in")

        # One strict comparison rule everywhere (B39): case and outer spaces only.
        from app.utils.email_match import UnsafeEmailError, normalise_email
        from app.api.v1.access import bootstrap_emails
        assert normalise_email("viewer_1@example.test") == "viewer_1@example.test"
        assert normalise_email(" \tViewer_1@EXAMPLE.test \n") == "viewer_1@example.test"
        assert normalise_email(None) == "" and normalise_email("   ") == ""
        lookalikes = [
            "vi\u0435wer_1@example.test",      # Cyrillic ie
            "viewer_1@ex\u0430mple.test",      # Cyrillic a, in the domain
            "vi\u03b5wer_1@example.test",      # Greek epsilon
            "viewer_1@example.t\u03bfst",      # Greek omicron
            "\u212aate@example.test",          # Kelvin sign, which lower() turns into "k"
            "\uff56iewer_1@example.test",      # fullwidth v, which NFKC turns into "v"
            "viewer\uff3f1@example.test",      # fullwidth low line
            "\u0130viewer_1@example.test",     # dotted capital I
            "viewer_1@example.test\u00a0",     # trailing no-break space
            "viewer_1@exa\u200bmple.test",     # zero-width space
        ]
        for lookalike in lookalikes:
            try:
                normalise_email(lookalike)
                raise AssertionError(f"compared unsafely: {lookalike!r}")
            except UnsafeEmailError:
                pass

        async def _lookalike_rules():
            async with async_session_maker() as db:
                for lookalike in lookalikes:
                    assert not await _email_is_allowed(db, lookalike), lookalike
                assert await _email_is_allowed(db, " VIEWER_1@example.test ")
                settings.ACCESS_BOOTSTRAP_EMAILS = "kate@example.test, \u212aate@example.test"
                try:
                    assert bootstrap_emails() == {"kate@example.test"}
                    assert not await _email_is_allowed(db, "\u212aate@example.test")
                    assert await _email_is_allowed(db, "Kate@Example.test")
                finally:
                    settings.ACCESS_BOOTSTRAP_EMAILS = ""
                user = await db.get(UserModel, "new_member")
                assert not await link_memberships(db, user, "p\u0435nding@example.test")

        asyncio.run(_lookalike_rules())
        print("   * Sign-in: emails match only letter for letter; look-alike letters never match")

        # More viewer limits: replan, supplier matching and the voice agent.
        assert c.post(f"/api/v1/weddings/{wedding_id}/replan", headers=viewer_headers).status_code == 403
        assert c.post(f"/api/v1/weddings/{wedding_id}/suppliers", json={"category": "photography"},
                      headers=viewer_headers).status_code == 403
        assert c.get("/api/v1/voice/token", headers=viewer_headers).status_code == 403
        print("   * Viewer: blocked from replan, supplier matching and the voice agent")

        # HS256 tokens: only with a configured secret, a matching signature and an expiry.
        import datetime as _dt
        exp = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=5)
        settings.JWT_SECRET = "test-only-secret-value-0123456789"
        try:
            def hs(secret, claims):
                tok = pyjwt.encode(claims, secret, algorithm="HS256")
                return c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
            assert hs("dev-jwt-secret-key-change-me-in-production",
                      {"sub": "couple_1", "exp": exp}).status_code == 401
            assert hs(settings.JWT_SECRET, {"sub": "couple_1"}).status_code == 401
            assert hs(settings.JWT_SECRET, {"sub": "nobody", "exp": exp}).status_code == 401
            res = hs(settings.JWT_SECRET, {"sub": "couple_1", "exp": exp, "role": "admin"})
            assert res.status_code == 200 and res.json()["role"] == "couple"
        finally:
            settings.JWT_SECRET = None
        print("   * Sign-in: HS256 needs the real secret and an expiry; the role comes from the database")

        # Firebase ID tokens, signed with a test RSA key in place of Google's.
        from cryptography.hazmat.primitives.asymmetric import rsa
        from app.api.v1.endpoints import auth as auth_module
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        class _FakeJwks:
            def get_signing_key_from_jwt(self, _token):
                return type("K", (), {"key": rsa_key.public_key()})()

        def firebase_headers(uid, email, verified):
            now = _dt.datetime.now(_dt.timezone.utc)
            tok = pyjwt.encode({
                "sub": uid, "email": email, "email_verified": verified,
                "iss": "https://securetoken.google.com/test-project", "aud": "test-project",
                "iat": now, "exp": now + _dt.timedelta(minutes=5),
            }, rsa_key, algorithm="RS256")
            return {"Authorization": f"Bearer {tok}"}

        # Pin the real public-key endpoint too: mocked JWTs alone did not catch
        # the old /jwks/ typo, which made every real sign-in fail with HTTP 401.
        assert auth_module.FIREBASE_JWKS_URL == (
            "https://www.googleapis.com/service_accounts/v1/jwk/"
            "securetoken@system.gserviceaccount.com"
        )
        from unittest.mock import patch
        auth_module._firebase_jwks_client.cache_clear()
        with patch.object(auth_module.jwt, "PyJWKClient") as key_client:
            auth_module._firebase_jwks_client()
            key_client.assert_called_once_with(auth_module.FIREBASE_JWKS_URL)
        auth_module._firebase_jwks_client.cache_clear()
        real_jwks = auth_module._firebase_jwks_client
        auth_module._firebase_jwks_client = lambda: _FakeJwks()
        settings.FIREBASE_PROJECT_ID = "test-project"
        settings.DEVELOPMENT_MODE = False
        settings.ACCESS_BOOTSTRAP_EMAILS = "newcouple@example.test"
        try:
            with Session(sync_engine) as s:
                s.add(WeddingMember(wedding_id=wedding_id, email="fam@example.test", level="viewer"))
                s.commit()
            res = c.get("/api/v1/auth/me", headers=firebase_headers("fb_stranger", "stranger@example.test", True))
            assert res.status_code == 403 and "isn't on the wedding's access list" in res.json()["detail"]
            res = c.get("/api/v1/auth/me", headers=firebase_headers("fb_fam", "FAM@example.test", False))
            assert res.status_code == 403 and "hasn't been confirmed" in res.json()["detail"]
            for uid, lookalike in (("fb_cyr", "f\u0430m@example.test"),
                                   ("fb_wide", "\uff46am@example.test")):
                res = c.get("/api/v1/auth/me", headers=firebase_headers(uid, lookalike, True))
                assert res.status_code == 403 and "can't check safely" in res.json()["detail"], res.text
            fam = firebase_headers("fb_fam", " FAM@example.test ", True)
            assert c.get("/api/v1/auth/me", headers=fam).status_code == 200
            assert c.get(f"/api/v1/weddings/{wedding_id}", headers=fam).status_code == 200
            assert c.patch(f"/api/v1/weddings/{wedding_id}", json={"guest_count_estimate": 1},
                           headers=fam).status_code == 403
            print("   * Firebase: unlisted, unconfirmed and look-alike emails refused; a listed viewer links and reads only")

            assert c.post("/api/v1/weddings/", json=wedding_payload, headers=fam).status_code == 403
            couple = firebase_headers("fb_newcouple", "newcouple@example.test", True)
            assert c.post("/api/v1/weddings/", json=dict(wedding_payload, wedding_date="2020-01-01"),
                          headers=couple).status_code == 422, "no past date at intake either"
            # "Today" pinned, so a run across midnight in Chicago can't fail falsely (B45).
            from app.utils import checklist as rules_now
            real_wedding_today = rules_now.wedding_today
            rules_now.wedding_today = lambda: D(2026, 11, 7)
            try:
                res = c.post("/api/v1/weddings/",
                             json=dict(wedding_payload, wedding_date="2027-08-21"),
                             headers=couple)
            finally:
                rules_now.wedding_today = real_wedding_today
            assert res.status_code == 201, res.text
            assert res.json()["wedding_date_set_on"] == "2026-11-07", \
                "a date given at intake counts as set that day (PD-007)"
            assert c.post("/api/v1/weddings/", json=wedding_payload, headers=couple).status_code == 409
            print("   * Weddings: only the couple's own email can create one, and only one")

            assert c.post("/tasks/intake-planner", json={"wedding_id": wedding_id}).status_code == 403
            settings.INTERNAL_TASKS_SECRET = "internal-test-secret"
            assert c.post("/tasks/quote-extractor", json={"booking_id": "x", "email_body": "y"},
                          headers={"X-Internal-Token": "wrong"}).status_code == 403
            assert c.post("/tasks/vendor-reply", json={
                "wedding_id": "x", "vendor_id": "x", "email_body": "y"}).status_code == 403
            assert c.post("/api/v1/webhooks/sendgrid/inbound",
                          data={"to": "booking-x@inbox.venueflow.ie", "text": "EUR 1"}).status_code == 403
            print("   * Worker routes and webhooks refuse calls without their secret")
        finally:
            auth_module._firebase_jwks_client = real_jwks
            settings.FIREBASE_PROJECT_ID = None
            settings.DEVELOPMENT_MODE = True
            settings.ACCESS_BOOTSTRAP_EMAILS = ""
            settings.INTERNAL_TASKS_SECRET = None
        
    print("\n--- ALL API SURFACE ENDPOINT INTEGRATION TESTS PASSED ---")

    # Clean up
    if os.path.exists("./endpoints_test.db"):
        os.remove("./endpoints_test.db")
        print("   Temporary database file cleaned up.")

if __name__ == "__main__":
    test_api_suite()
