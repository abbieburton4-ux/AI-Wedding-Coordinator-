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
        
        # 3. Auth Router
        print("3. Verifying planner auth login endpoints...")
        # Success Auth Path
        res = c.post("/api/v1/auth/planner", json={"email": "maryaoife@weddingwonders.ie"})
        assert res.status_code == 200
        auth_data = res.json()
        assert "token" in auth_data
        assert auth_data["role"] == "planner"
        token = auth_data["token"]
        print(f"   * Login Success: Obtained token '{token}'")
        
        # Unauthorized check: invalid roles
        res = c.post("/api/v1/auth/planner", json={"email": "clara.sean@wedding.ie"})
        assert res.status_code == 403
        print("   * Login Safeguard: Successfully blocked non-planner email login")
        
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
        res = c.post("/api/v1/weddings/", json=wedding_payload, headers=headers)
        assert res.status_code == 201
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
        res = c.post("/api/v1/inquiries/booking_photo_test/quote", json=quote_payload, headers=headers)
        assert res.status_code == 202
        assert res.json()["status"] == "pending"
        print("   * Enqueue: Quote Extractor enqueued successfully")
        
        # 7. Decision Logs & Masked CSV exports
        print("7. Verifying decision logs and PII-redacted CSV exports...")
        res = c.get(f"/api/v1/weddings/{wedding_id}/decisions", headers=headers)
        assert res.status_code == 200
        logs = res.json()
        print(f"   * Logs read: Fetched {len(logs)} decision log traces")
        
        # Export Redacted CSV (use dynamically created wedding owned by our planner)
        res = c.get(f"/api/v1/weddings/{wedding_id}/decisions/export", headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        csv_content = res.text
        # Verify PII masking: no raw emails should leak through
        assert "clara.sean@wedding.ie" not in csv_content
        print(f"   * Export: CSV downloaded ({len(csv_content)} bytes), PII masking verified")
        
        # 8. Operational Telemetry Metrics
        print("8. Verifying metrics dashboard calculations...")
        res = c.get("/api/v1/metrics", headers=headers)
        assert res.status_code == 200
        metrics = res.json()
        assert "total_weddings" in metrics
        assert "total_decisions_executed" in metrics
        assert "conversions" in metrics
        print(f"   * Telemetry success: Total Weddings={metrics['total_weddings']}, Decisions={metrics['total_decisions_executed']}")
        
    print("\n--- ALL API SURFACE ENDPOINT INTEGRATION TESTS PASSED ---")

    # Clean up
    if os.path.exists("./endpoints_test.db"):
        os.remove("./endpoints_test.db")
        print("   Temporary database file cleaned up.")

if __name__ == "__main__":
    test_api_suite()
