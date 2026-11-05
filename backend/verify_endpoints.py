import os
import sys
from fastapi.testclient import TestClient

# Override environments for local SQLite test session
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./endpoints_test.db"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///./endpoints_test.db"
os.environ["DEVELOPMENT_MODE"] = "True"
os.environ["ALLOW_MOCK_AUTH"] = "True"

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
        
        # Verify access control
        unauth_headers = {"Authorization": "Bearer mock-couple_2"}
        res = c.get(f"/api/v1/weddings/{wedding_id}", headers=unauth_headers)
        assert res.status_code == 403
        print("   * Access Control: Correctly blocked unauthorized couple from reading wedding details")
        
        # 5. Matching endpoints
        print("5. Verifying matching triggers (P0 background tasks enqueuing)...")
        # Venue Matching
        res = c.post(f"/api/v1/weddings/{wedding_id}/match", headers=headers)
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Venue Matcher enqueued successfully")
        
        # Supplier Matching
        res = c.post(f"/api/v1/weddings/{wedding_id}/suppliers", json={"category": "photography"}, headers=headers)
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
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Quote Extractor enqueued successfully")
        res = c.post("/api/v1/inquiries/booking_photo_test/quote", json=quote_payload, headers=headers)
        assert res.status_code == 403
        print("   * Access Control: blocked quote extraction on another wedding's booking")
        
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
                                "overpaid_cents": 0, "contributions_cents": 600_000}
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
        assert c.delete(f"{b_url}/categories/{cake_cat}", headers=headers).status_code == 204
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
            calls.append(kwargs)
            return {"suggestion": True, "total_cents": kwargs["total_cents"],
                    "lines": [{"name": "Venue", "planned_cents": 3_000_000, "existing": True,
                               "rationale": "r"},
                              {"name": "Catering", "planned_cents": 1_000_000,
                               "existing": False, "rationale": "r"}],
                    "rationale_summary": "s"}

        async def _blocked_split(db, wid, **kwargs):
            return {"status": "blocked", "error_kind": "category_whitelist"}

        budget_module.run_budget_splitter = _fake_split
        try:
            res = c.post(f"{b_url}/suggest-split", headers=headers)
            assert res.status_code == 200 and len(res.json()["lines"]) == 2, res.text
            assert calls[0]["total_cents"] == 4_000_000
            assert sorted(calls[0]["category_names"]) == ["Florals", "Venue"]
            budget_module.run_budget_splitter = _blocked_split
            assert c.post(f"{b_url}/suggest-split", headers=headers).status_code == 422
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
            ("post", f"{b_url}/contributions",
             {"contributor": "Z", "amount_cents": 1, "category_id": o_cat}),
            ("patch", f"{b_url}/contributions/{my_con}", {"category_id": o_cat}),
        ]
        for method, url, body in cross:
            kwargs = {"headers": headers}
            if body is not None:
                kwargs["json"] = body
            res = c.request(method.upper(), url, **kwargs)
            assert res.status_code == 404, (method, url, res.status_code)
        theirs = c.get(f"{o_url}/overview", headers=other_headers).json()
        assert [cat["name"] for cat in theirs["categories"]] == ["Their venue"]
        their_pay = theirs["categories"][0]["costs"][0]["payments"][0]
        assert (their_pay["amount_cents"], their_pay["paid"]) == (100, False)
        assert [con["amount_cents"] for con in theirs["contributions"]] == [100]
        ours = c.get(f"{b_url}/overview", headers=headers).json()
        assert all(cat["id"] != o_cat for cat in ours["categories"])
        assert next(cat for cat in ours["categories"] if cat["id"] == mine)["costs"][0][
            "id"] == my_cost, "the cost stayed in this wedding's category"
        assert all(con["category_id"] is None for con in ours["contributions"])
        print("   * Cross-wedding: another wedding's real ids are refused (404) and untouched")

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
            assert c.post("/api/v1/weddings/", json=wedding_payload, headers=couple).status_code == 201
            assert c.post("/api/v1/weddings/", json=wedding_payload, headers=couple).status_code == 409
            print("   * Weddings: only the couple's own email can create one, and only one")

            assert c.post("/tasks/intake-planner", json={"wedding_id": wedding_id}).status_code == 403
            settings.INTERNAL_TASKS_SECRET = "internal-test-secret"
            assert c.post("/tasks/quote-extractor", json={"booking_id": "x", "email_body": "y"},
                          headers={"X-Internal-Token": "wrong"}).status_code == 403
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
