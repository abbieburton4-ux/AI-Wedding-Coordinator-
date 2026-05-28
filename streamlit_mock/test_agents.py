import pytest
import json
import os
import uuid
from unittest.mock import patch, MagicMock
import db
import agents
import constants

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


# ==========================================
# 5. TEST CATEGORY WHITELIST GUARDRAIL
# ==========================================

def test_intake_planner_blocks_invalid_categories(mock_client):
    """A budget_line with a non-canonical category should block the run and
    leave no budget_lines behind. Covers commit 1bb2b3ce."""
    mock_response_data = {
        "is_budget_realistic": True,
        "guardrail_warning": "",
        "budget_lines": [
            {"category": "venue", "allocated_amount": 12000.0, "rationale": "Venue rental"},
            {"category": "decor", "allocated_amount": 3000.0, "rationale": "Decorations"},
        ],
        "timeline_items": [],
        "rationale_summary": "Plan including decor line",
        "confidence_score": 0.85,
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    res = agents.run_intake_planner("wedding_intake_test", user_id="couple_1")

    assert res["status"] == "blocked"
    assert "decor" in res["warning"]

    logs = db.get_agent_logs("wedding_intake_test")
    assert len(logs) == 1
    assert logs[0]["status"] == "blocked_by_guardrail"
    assert logs[0]["error_kind"] == "category_whitelist"

    # No budget_lines should have been inserted — guardrail runs before mutation.
    assert db.get_budget_lines("wedding_intake_test") == []


def test_intake_planner_normalizes_category_case(mock_client):
    """A capitalized category like 'Venue' should be normalized to 'venue' and
    accepted, not falsely blocked by the whitelist. Covers commit 61f34bb2."""
    mock_response_data = {
        "is_budget_realistic": True,
        "guardrail_warning": "",
        "budget_lines": [
            {"category": "Venue", "allocated_amount": 12000.0, "rationale": "Capitalized"},
            {"category": "  Florals  ", "allocated_amount": 2000.0, "rationale": "Padded"},
        ],
        "timeline_items": [],
        "rationale_summary": "Mixed-case categories",
        "confidence_score": 0.9,
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    res = agents.run_intake_planner("wedding_intake_test", user_id="couple_1")

    assert res["status"] == "success", "Capitalized/padded canonical categories must not be blocked"

    # Inserted categories must be normalized so downstream WHERE category = ? matches.
    lines = db.get_budget_lines("wedding_intake_test")
    stored_categories = sorted(line["category"] for line in lines)
    assert stored_categories == ["florals", "venue"]


# ==========================================
# 6. TEST IRISH REGION HIERARCHY (B4)
# ==========================================

def test_region_matches_handles_province_and_county():
    """B4: region_matches must accept county↔province in both directions and
    return False for cross-province pairs."""
    rm = constants.region_matches

    # Exact county match
    assert rm("Sligo", "Sligo")

    # Province → constituent county (both directions)
    assert rm("Meath", "Leinster")
    assert rm("Leinster", "Meath")
    assert rm("Sligo", "Connacht")
    assert rm("Connacht", "Sligo")
    assert rm("Clare", "Munster")
    assert rm("Monaghan", "Ulster")

    # Province → province (same)
    assert rm("Leinster", "Leinster")

    # Cross-province: no match
    assert not rm("Sligo", "Leinster")     # Sligo is Connacht
    assert not rm("Clare", "Connacht")     # Clare is Munster
    assert not rm("Monaghan", "Leinster")  # Monaghan is Ulster

    # County to unrelated county
    assert not rm("Sligo", "Meath")


def test_venue_matcher_leinster_selection_includes_meath_venues(mock_client):
    """B4: a couple picking 'Leinster' province should see Millhouse Slane
    (Meath) in the pre-LLM candidate list, not just venues seeded literally
    as 'Leinster'."""
    # Set up a Leinster wedding
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO weddings (id, couple_user_id, status, budget_total, currency, region, ceremony_type, guest_count_estimate)
        VALUES ('wedding_leinster', 'couple_1', 'planning', 30000.0, 'EUR', 'Leinster', 'Civil/Humanist', 100);
    """)
    conn.commit()
    conn.close()

    # Benign LLM response — we're not testing the LLM, we're testing the
    # input_payload constructed by the pre-filter.
    mock_response_data = {
        "shortlist": [{
            "vendor_id": "venue_millhouse",
            "rank": 1,
            "matching_rationale": "Meath venue for Leinster wedding",
            "draft_inquiry_email": "Dear Millhouse...",
        }],
        "rationale_summary": "Picked Millhouse",
        "confidence_score": 0.9,
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    agents.run_venue_matcher("wedding_leinster", user_id="planner_1")

    # Inspect what was sent to Gemini
    prompt_sent = mock_client.models.generate_content.call_args.kwargs["contents"]
    payload = json.loads(prompt_sent.split("\n", 1)[1])
    venue_names = {v["name"] for v in payload["available_venues"]}
    venue_regions = {v["region"] for v in payload["available_venues"]}

    # Millhouse Slane (Meath) and Tullamore GAA (Leinster) should both be
    # in the in-region candidates because expand_region("Leinster") covers
    # Meath, Offaly, etc.
    assert "The Millhouse Slane" in venue_names, f"Got {venue_names}"
    assert "Tullamore GAA Clubhouse Hall" in venue_names

    # And the region-match count reflects the hierarchy (>= 2)
    assert payload["wedding_profile"]["venues_matching_region_count"] >= 2


# ==========================================
# 7. TEST QUOTE_EXTRACT PARENT CHAIN
# ==========================================

def _set_matcher_response(mock_client, vendor_id="venue_castle_leslie"):
    """Mock helper: set Gemini's next response to a minimal valid matcher result."""
    mock_client.models.generate_content.return_value = MockResponse(json.dumps({
        "shortlist": [{
            "vendor_id": vendor_id,
            "rank": 1,
            "matching_rationale": "Test rationale",
            "draft_inquiry_email": "Test email",
        }],
        "rationale_summary": "Test match",
        "confidence_score": 0.9,
    }))


def _set_extractor_response(mock_client):
    """Mock helper: set Gemini's next response to a minimal valid quote extraction."""
    mock_client.models.generate_content.return_value = MockResponse(json.dumps({
        "is_available": True,
        "line_items": [{"item": "Hire", "description": "Venue hire", "amount": 5000.0}],
        "total_amount": 5000.0,
        "currency": "EUR",
        "rationale_text": "Quote extracted from test email",
        "confidence_score": 0.95,
    }))


def _booking_id_for(wedding_id):
    bookings = db.get_bookings(wedding_id)
    assert bookings, f"No bookings found for {wedding_id}"
    return bookings[0]["id"]


def test_quote_extract_chains_to_inquiry_send(mock_client):
    """Full 3-level chain: matcher → inquiry_send → quote_extract. The
    quote_extract log's parent_decision_id must point at the inquiry_send,
    not the matcher, because inquiry_send is the direct trigger for the
    supplier reply we just parsed."""
    # 1. Matcher creates the booking, with sourced_by_agent_id = matcher log id.
    _set_matcher_response(mock_client)
    matcher_res = agents.run_venue_matcher("wedding_intake_test", user_id="planner_1")
    matcher_log_id = matcher_res["log_id"]
    booking_id = _booking_id_for("wedding_intake_test")

    # 2. Simulate the UI's inquiry-send action.
    inquiry_send_id = str(uuid.uuid4())
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agent_decision_logs
            (id, agent_id, wedding_id, booking_id, parent_decision_id,
             trigger, decision_type, status, rationale_summary)
        VALUES (?, 'system', 'wedding_intake_test', ?, ?,
                'couple_action', 'inquiry_send', 'success', 'sent inquiry')
    """, (inquiry_send_id, booking_id, matcher_log_id))
    conn.commit()
    conn.close()

    # 3. Quote extractor parses the supplier reply.
    _set_extractor_response(mock_client)
    extract_res = agents.run_quote_extractor(booking_id, "Test email", user_id="planner_1")

    # 4. Verify parent chain: quote_draft → inquiry_send → venue_match
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT parent_decision_id FROM agent_decision_logs WHERE id = ?",
        (extract_res["log_id"],),
    )
    quote_parent = cursor.fetchone()[0]
    cursor.execute(
        "SELECT parent_decision_id FROM agent_decision_logs WHERE id = ?",
        (inquiry_send_id,),
    )
    inquiry_parent = cursor.fetchone()[0]
    conn.close()

    assert quote_parent == inquiry_send_id, (
        f"quote_draft should chain to inquiry_send. Got parent={quote_parent}, "
        f"expected={inquiry_send_id}"
    )
    assert inquiry_parent == matcher_log_id, "inquiry_send should chain to matcher"


def test_quote_extract_falls_back_to_matcher_when_no_inquiry_send(mock_client):
    """If quote_extract runs without an intervening inquiry_send log (e.g.,
    the supplier replied before the UI marked the inquiry as sent), parent
    falls back to the matcher decision via booking.sourced_by_agent_id."""
    _set_matcher_response(mock_client)
    matcher_res = agents.run_venue_matcher("wedding_intake_test", user_id="planner_1")
    matcher_log_id = matcher_res["log_id"]
    booking_id = _booking_id_for("wedding_intake_test")

    # No inquiry_send. Straight to quote extraction.
    _set_extractor_response(mock_client)
    extract_res = agents.run_quote_extractor(booking_id, "Test email", user_id="planner_1")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT parent_decision_id FROM agent_decision_logs WHERE id = ?",
        (extract_res["log_id"],),
    )
    parent = cursor.fetchone()[0]
    conn.close()

    assert parent == matcher_log_id, (
        f"With no inquiry_send, parent should fall back to matcher log "
        f"({matcher_log_id}). Got {parent}."
    )


# ==========================================
# 8. TEST USER-ACTION LOG HELPERS
# ==========================================

def test_log_user_action_writes_a_row_with_expected_fields():
    """Sanity check: log_user_action inserts exactly the fields the caller
    provides, with agent_id='system' and an empty external_api_calls."""
    conn = db.get_connection()
    cursor = conn.cursor()
    log_id = agents.log_user_action(
        cursor,
        wedding_id="wedding_intake_test",
        decision_type="inquiry_send",
        rationale_summary="Sent inquiry to Castle Leslie.",
        booking_id=None,
        parent_decision_id=None,
        user_id="planner_1",
    )
    conn.commit()
    cursor.execute("SELECT * FROM agent_decision_logs WHERE id = ?", (log_id,))
    row = dict(cursor.fetchone())
    conn.close()

    assert row["agent_id"] == "system"
    assert row["decision_type"] == "inquiry_send"
    assert row["status"] == "success"
    assert row["user_id"] == "planner_1"
    assert row["rationale_summary"] == "Sent inquiry to Castle Leslie."
    assert row["external_api_calls"] == "[]"


def test_log_user_override_marks_parent_and_inserts_child():
    """log_user_override updates the parent's overridden_by_user_id AND
    inserts a dedicated override_option child log. Both writes happen in
    a single helper call so the audit pair stays consistent."""
    # Set up a parent agent decision via a direct INSERT (we're testing
    # the helper, not the agent flow).
    conn = db.get_connection()
    cursor = conn.cursor()
    parent_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO agent_decision_logs
            (id, agent_id, wedding_id, trigger, decision_type, status, rationale_summary)
        VALUES (?, 'venue_matcher', 'wedding_intake_test', 'couple_action',
                'venue_match', 'success', 'Matched venues')
    """, (parent_id,))
    conn.commit()

    child_id = agents.log_user_override(
        cursor,
        parent_decision_id=parent_id,
        overridden_by_user_id="planner_1",
        wedding_id="wedding_intake_test",
        rationale_summary="Declined Castle Leslie - too expensive.",
    )
    conn.commit()

    # Parent now has overridden_by_user_id set
    cursor.execute("SELECT overridden_by_user_id FROM agent_decision_logs WHERE id = ?", (parent_id,))
    assert cursor.fetchone()[0] == "planner_1"

    # Child exists with parent link
    cursor.execute("""
        SELECT decision_type, parent_decision_id, overridden_by_user_id
        FROM agent_decision_logs WHERE id = ?
    """, (child_id,))
    child = cursor.fetchone()
    conn.close()
    assert child[0] == "override_option"
    assert child[1] == parent_id
    assert child[2] == "planner_1"


def test_resolve_quote_accept_parent_finds_latest_quote_draft():
    """_resolve_quote_accept_parent picks the most recent successful
    quote_draft for the booking — closes the 4-level chain
    matcher → inquiry_send → quote_draft → quote_accept."""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Insert two quote_draft logs for the same booking, then check we
    # get the latest one.
    older = str(uuid.uuid4())
    newer = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, wedding_id, booking_id,
            trigger, decision_type, status, rationale_summary, timestamp)
        VALUES (?, 'quote_extractor', 'wedding_planning_test', 'booking_photo_test',
                'supplier_response', 'quote_draft', 'success', 'first quote',
                '2026-05-20 10:00:00')
    """, (older,))
    cursor.execute("""
        INSERT INTO agent_decision_logs (id, agent_id, wedding_id, booking_id,
            trigger, decision_type, status, rationale_summary, timestamp)
        VALUES (?, 'quote_extractor', 'wedding_planning_test', 'booking_photo_test',
                'supplier_response', 'quote_draft', 'success', 'second quote',
                '2026-05-21 14:00:00')
    """, (newer,))
    conn.commit()

    resolved = agents._resolve_quote_accept_parent(cursor, "booking_photo_test")
    conn.close()
    assert resolved == newer, "Should pick the newer quote_draft for chaining"


# ==========================================
# 9. TEST LIVE-REASONING on_step CALLBACK
# ==========================================

def test_venue_matcher_emits_progress_steps_on_success(mock_client, capsys):
    """The on_step callback must fire at every major checkpoint with messages
    that contain real values from the wedding profile + decision-log metadata.
    Streamlit consumes the same callback to render the live status block."""
    mock_response_data = {
        "shortlist": [
            {
                "vendor_id": "venue_castle_leslie",
                "rank": 1,
                "matching_rationale": "Connacht fallback - exclusive country house",
                "draft_inquiry_email": "Dear Castle Leslie...",
            }
        ],
        "rationale_summary": "Picked Castle Leslie",
        "confidence_score": 0.87,
    }
    mock_client.models.generate_content.return_value = MockResponse(
        json.dumps(mock_response_data), prompt_tokens=1200, output_tokens=2847,
    )

    captured = []
    res = agents.run_venue_matcher(
        "wedding_intake_test",
        user_id="planner_1",
        on_step=lambda msg: captured.append(msg),
    )
    assert res["status"] == "success"

    # Print the actual narration the UI would render — visible in -s mode.
    print("\n--- Live-reasoning trail (what the user sees) ---")
    for i, line in enumerate(captured, 1):
        print(f"  {i}. {line}")
    print("--- end ---\n")

    # Contract: at least the 5 deterministic checkpoints + 1 final log-write line.
    assert len(captured) >= 5, f"Expected ≥5 steps, got {len(captured)}: {captured}"

    joined = " | ".join(captured).lower()
    assert "wedding profile" in joined, "missing profile-load step"
    assert "filtered" in joined and "guests" in joined, "missing capacity-filter step"
    assert "sligo" in joined, "wedding_intake_test region (Sligo) must surface in narration"
    assert "asking gemini" in joined, "missing pre-LLM step"
    assert "tokens" in joined and "confidence" in joined, "missing post-LLM stats step"
    assert "logged decision" in joined, "missing audit-log confirmation step"


def test_intake_planner_emits_progress_steps_on_success(mock_client, capsys):
    """intake_planner narrates: profile read, Gemini call, response stats,
    success summary (budget categories + timeline), audit-log write."""
    mock_response_data = {
        "is_budget_realistic": True,
        "guardrail_warning": "",
        "budget_lines": [
            {"category": "venue", "allocated_amount": 12000.0, "rationale": "Venue rental"},
            {"category": "catering", "allocated_amount": 10000.0, "rationale": "Per-head 100 guests"},
            {"category": "photography", "allocated_amount": 2500.0, "rationale": "Documentary"},
        ],
        "timeline_items": [
            {"title": "Book Venue", "description": "...", "months_before": 12.0, "kind": "planning"},
            {"title": "HSE Notification", "description": "...", "months_before": 3.0, "kind": "planning"},
        ],
        "rationale_summary": "Seeded plan for Sligo Civil/Humanist wedding.",
        "confidence_score": 0.92,
    }
    mock_client.models.generate_content.return_value = MockResponse(
        json.dumps(mock_response_data), prompt_tokens=1500, output_tokens=3100,
    )

    captured = []
    res = agents.run_intake_planner(
        "wedding_intake_test",
        user_id="couple_1",
        on_step=lambda msg: captured.append(msg),
    )
    assert res["status"] == "success"

    print("\n--- intake_planner live-reasoning trail ---")
    for i, line in enumerate(captured, 1):
        print(f"  {i}. {line}")
    print("--- end ---\n")

    assert len(captured) >= 5
    joined = " | ".join(captured).lower()
    assert "reading intake" in joined and "sligo" in joined and "civil/humanist" in joined, (
        f"profile-read step should name region + ceremony_type: {captured}"
    )
    assert "asking gemini" in joined, "missing pre-LLM step"
    assert "tokens" in joined and "confidence" in joined, "missing post-LLM stats step"
    assert "drafted" in joined and "categories" in joined and "milestones" in joined, (
        "missing success summary step"
    )
    assert "logged decision" in joined, "missing audit-log confirmation"


def test_intake_planner_emits_blocked_step_on_budget_guardrail(mock_client):
    """When Gemini returns is_budget_realistic=false, the on_step callback
    must surface the budget-realism rejection so the user sees the AI's
    reasoning, not just an error code."""
    mock_response_data = {
        "is_budget_realistic": False,
        "guardrail_warning": (
            "€2,000 is insufficient for 200 guests in Dublin. Catering alone "
            "would exceed €15,000 at Irish market rates."
        ),
        "budget_lines": [],
        "timeline_items": [],
        "rationale_summary": "Budget unrealistic for stated guest count.",
        "confidence_score": 0.95,
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    # Use the planning-test wedding which the seed leaves in 'planning' status —
    # intake_planner accepts any status for the agent's purposes, the guardrail
    # check is independent of wedding status.
    captured = []
    res = agents.run_intake_planner(
        "wedding_intake_test",
        user_id="couple_1",
        on_step=lambda msg: captured.append(msg),
    )
    assert res["status"] == "blocked"

    blocked_line = next((line for line in captured if "realism check failed" in line.lower()), None)
    assert blocked_line is not None, (
        f"Expected a 'Budget realism check failed' narration. Got: {captured}"
    )
    assert "200 guests" in blocked_line or "dublin" in blocked_line.lower(), (
        "Blocked step should surface the AI's specific reasoning, not just generic 'blocked'"
    )


def test_venue_matcher_emits_blocked_step_on_hallucination(mock_client):
    """When the LLM hallucinates a venue_id, the on_step callback must surface
    a 'Blocked' message so the user sees WHY the run stopped — not just that
    it did. This is the security-theatre moment that builds trust."""
    mock_response_data = {
        "shortlist": [
            {"vendor_id": "venue_castle_leslie", "rank": 1,
             "matching_rationale": "ok", "draft_inquiry_email": "..."},
            {"vendor_id": "venue_imaginary_palace", "rank": 2,
             "matching_rationale": "fake", "draft_inquiry_email": "..."},
        ],
        "rationale_summary": "Mixed real and imaginary",
        "confidence_score": 0.5,
    }
    mock_client.models.generate_content.return_value = MockResponse(json.dumps(mock_response_data))

    captured = []
    res = agents.run_venue_matcher(
        "wedding_intake_test",
        user_id="planner_1",
        on_step=lambda msg: captured.append(msg),
    )
    assert res["status"] == "blocked"

    blocked_line = next((line for line in captured if "blocked" in line.lower()), None)
    assert blocked_line is not None, f"Expected a 'Blocked' step. Got: {captured}"
    assert "venue_imaginary_palace" in blocked_line, "The hallucinated id must be named in the narration"


# ==========================================
# 10. TEST PENDING-LOG ORPHAN INVARIANT
# ==========================================

def test_intake_planner_no_orphan_pending_on_missing_wedding(mock_client):
    """A missing wedding_id must not leave orphan 'pending' rows in the
    audit trail — the invariant commit 874e42ca promised. After B1, the
    agent raises ValueError before opening the pending log, so no row is
    created at all. Either mechanism satisfies the audit invariant."""
    with pytest.raises(ValueError):
        agents.run_intake_planner("does-not-exist", user_id="couple_1")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, wedding_id FROM agent_decision_logs WHERE status = 'pending'")
    pending_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    assert pending_rows == [], (
        f"Audit trail polluted: {len(pending_rows)} 'pending' rows remain after a failed "
        f"run. Commit 874e42ca's invariant says no agent decision should sit in 'pending'."
    )


def test_agents_raise_value_error_on_missing_wedding(mock_client):
    """B1: intake_planner, venue_matcher, and supplier_matcher must all
    raise ValueError immediately when wedding_id doesn't exist — before any
    pending log row is opened. Distinguishes 'bad caller' from 'Gemini
    failure' so the caller can decide whether to retry."""
    bogus_id = "wedding-does-not-exist"

    with pytest.raises(ValueError, match="Wedding not found"):
        agents.run_intake_planner(bogus_id, user_id="couple_1")
    with pytest.raises(ValueError, match="Wedding not found"):
        agents.run_venue_matcher(bogus_id, user_id="planner_1")
    with pytest.raises(ValueError, match="Wedding not found"):
        agents.run_supplier_matcher(bogus_id, "photography", user_id="planner_1")

    # Zero log rows for the bogus id — the FK didn't even get a chance to
    # reject anything because we never tried to INSERT.
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM agent_decision_logs WHERE wedding_id = ?", (bogus_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0, f"Expected 0 log rows for missing wedding, got {count}"
