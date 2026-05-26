import pytest
import json
import os
import uuid
from unittest.mock import patch, MagicMock
import db
import agents

# Helpers for mocking Gemini response objects

class MockUsageMetadata:
    def __init__(self, prompt_token_count=15, candidates_token_count=25):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count

class MockResponse:
    def __init__(self, text, prompt_tokens=15, output_tokens=25):
        self.text = text
        self.usage_metadata = MockUsageMetadata(prompt_tokens, output_tokens)


@pytest.fixture(autouse=True)
def setup_database():
    """Initializes and seeds the database before each test to ensure a clean state."""
    db.init_db(force=True)


@pytest.fixture
def mock_client():
    """Mocks the genai.Client and patches the get_client function to return it."""
    client = MagicMock()
    with patch("agents.get_client", return_value=client):
        yield client


# ==========================================
# 1. TEST INTAKE PLANNER GUARDRAILS
# ==========================================

def test_intake_planner_guardrail_unrealistic_budget(mock_client):
    """Verifies that the intake planner blocks an unrealistic budget and logs it correctly."""
    # Insert temporary wedding with unrealistic budget
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO weddings (id, couple_user_id, status, budget_total, currency, region, ceremony_type, guest_count_estimate)
        VALUES ('wedding_unrealistic', 'couple_1', 'intake', 2000.0, 'EUR', 'Dublin', 'Civil/Humanist', 200);
    """)
    conn.commit()
    conn.close()

    # Mock unrealistic budget LLM response
    mock_response_data = {
        "is_budget_realistic": False,
        "guardrail_warning": "Dublin weddings require at least €75 per head for catering alone. €2,000 is insufficient for 200 guests.",
        "budget_lines": [],
        "timeline_items": [],
        "rationale_summary": "Budget is too low for 200 guests in Dublin.",
        "confidence_score": 0.95
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    # Run the planner
    res = agents.run_intake_planner("wedding_unrealistic", user_id="couple_1")
    
    assert res["status"] == "blocked"
    assert "€2,000 is insufficient for 200 guests" in res["warning"]

    # Verify database log entry
    logs = db.get_agent_logs("wedding_unrealistic")
    assert len(logs) == 1
    assert logs[0]["status"] == "blocked_by_guardrail"
    assert logs[0]["error_kind"] == "intake_validation"
    assert logs[0]["user_id"] == "couple_1"
    
    # Check that external_api_calls has been wired
    calls = json.loads(logs[0]["external_api_calls"])
    assert len(calls) == 1
    assert calls[0]["provider"] == "google"


def test_intake_planner_success(mock_client):
    """Verifies that the intake planner succeeds, seeds budget lines/timeline, and logs properly."""
    # Mock realistic plan response
    mock_response_data = {
        "is_budget_realistic": True,
        "guardrail_warning": "",
        "budget_lines": [
            {"category": "venue", "allocated_amount": 12000.0, "rationale": "Exclusive venue rental"},
            {"category": "catering", "allocated_amount": 10000.0, "rationale": "Buffet for 100 guests"}
        ],
        "timeline_items": [
            {"title": "Book Venue", "description": "Choose and book Irish castle", "months_before": 12.0, "kind": "planning"},
            {"title": "HSE Notification", "description": "Notify HSE registry office", "months_before": 3.0, "kind": "planning"}
        ],
        "rationale_summary": "Seeded budget and timeline successfully.",
        "confidence_score": 0.9
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    # Run planner on realistic preset wedding
    res = agents.run_intake_planner("wedding_intake_test", user_id="couple_1")
    
    assert res["status"] == "success"
    
    # Verify budget and timeline rows were seeded
    lines = db.get_budget_lines("wedding_intake_test")
    assert len(lines) == 2
    assert any(line["category"] == "venue" and line["allocated_amount"] == 12000.0 for line in lines)
    
    timeline = db.get_timeline_items("wedding_intake_test")
    assert len(timeline) == 2
    assert any(t["title"] == "Book Venue" for t in timeline)

    # Verify log entry
    logs = db.get_agent_logs("wedding_intake_test")
    assert logs[0]["status"] == "success"
    assert logs[0]["user_id"] == "couple_1"
    assert logs[0]["prompt_version"].startswith("v1.0-")


# ==========================================
# 2. TEST MATCHER HALLUCINATION GUARDRAILS
# ==========================================

def test_venue_matcher_hallucination_block(mock_client):
    """Verifies that the venue matcher blocks and doesn't write when a vendor ID is hallucinated."""
    # Mock LLM return containing a hallucinated ID not present in the pre-filtered seed list
    mock_response_data = {
        "shortlist": [
            {
                "vendor_id": "venue_castle_leslie", # Valid
                "rank": 1,
                "matching_rationale": "Fits constraints",
                "draft_inquiry_email": "Dear Leslie..."
            },
            {
                "vendor_id": "venue_imaginary_castle", # Hallucinated!
                "rank": 2,
                "matching_rationale": "Gothic styling",
                "draft_inquiry_email": "Hello imaginary..."
            }
        ],
        "rationale_summary": "Matched two venues",
        "confidence_score": 0.85
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    # Run venue matcher
    res = agents.run_venue_matcher("wedding_intake_test", user_id="planner_1")
    
    assert res["status"] == "blocked"
    assert "Hallucinated venue IDs detected" in res["warning"]

    # Verify that NO bookings were inserted
    bookings = db.get_bookings("wedding_intake_test")
    assert len(bookings) == 0

    # Verify database log entry shows guardrail blocked
    logs = db.get_agent_logs("wedding_intake_test")
    matcher_log = next(l for l in logs if l["decision_type"] == "venue_match")
    assert matcher_log["status"] == "blocked_by_guardrail"
    assert matcher_log["error_kind"] == "hallucination_guardrail"
    assert "venue_imaginary_castle" in matcher_log["error_message"]


# ==========================================
# 3. TEST MATCHER IDEMPOTENCY
# ==========================================

def test_matcher_idempotency(mock_client):
    """Verifies that running the venue matcher twice does not insert duplicate booking records."""
    # Mock valid venue list response
    mock_response_data = {
        "shortlist": [
            {
                "vendor_id": "venue_castle_leslie",
                "rank": 1,
                "matching_rationale": "Matches Leinster region capacity",
                "draft_inquiry_email": "Inquiry Leslie"
            }
        ],
        "rationale_summary": "Matched Castle Leslie",
        "confidence_score": 0.95
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    # Run the matcher the first time
    res1 = agents.run_venue_matcher("wedding_intake_test", user_id="planner_1")
    assert res1["status"] == "success"
    
    bookings_after_run1 = db.get_bookings("wedding_intake_test")
    assert len(bookings_after_run1) == 1
    booking_id = bookings_after_run1[0]["id"]

    # Run the matcher a second time with same mock response
    res2 = agents.run_venue_matcher("wedding_intake_test", user_id="planner_1")
    assert res2["status"] == "success"

    # Verify that the booking was NOT duplicated
    bookings_after_run2 = db.get_bookings("wedding_intake_test")
    assert len(bookings_after_run2) == 1
    assert bookings_after_run2[0]["id"] == booking_id


# ==========================================
# 4. TEST SCHEMA / API EXCEPTION HANDLING & ROLLBACK
# ==========================================

def test_agent_error_rollback(mock_client):
    """Verifies that exceptions are caught, transaction is rolled back, and log is set to error."""
    # Mock LLM to throw an API exception mid-flight
    mock_client.models.generate_content.side_effect = Exception("Gemini service quota exceeded")

    with pytest.raises(Exception, match="Gemini service quota exceeded"):
        agents.run_intake_planner("wedding_intake_test", user_id="couple_1")

    # Verify database log entry is marked as 'error'
    logs = db.get_agent_logs("wedding_intake_test")
    assert len(logs) == 1
    assert logs[0]["status"] == "error"
    assert logs[0]["error_kind"] == "api_error"
    assert "quota exceeded" in logs[0]["error_message"]

    # Verify no timeline or budget lines were seeded (rollback worked)
    lines = db.get_budget_lines("wedding_intake_test")
    assert len(lines) == 0
    timeline = db.get_timeline_items("wedding_intake_test")
    assert len(timeline) == 0
