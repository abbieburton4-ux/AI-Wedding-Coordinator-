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
