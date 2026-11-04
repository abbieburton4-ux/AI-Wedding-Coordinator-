# VenueFlow — Streamlit AI Wedding Coordinator Mock

This directory contains the Python Streamlit mockup application for the VenueFlow AI Wedding Coordinator, showcasing the end-to-end agent workflows (intake validation, venue and supplier matching, quote extraction, and budget alerts) backed by SQLite.

## How to Run

1. **Set Up a Virtual Environment & Install Dependencies**:
   ```bash
   cd streamlit_mock
   python3 -m venv .venv
   source .venv/bin/pip install -r requirements.txt
   ```

2. **Configure Your Environment**:
   Export your Gemini API Key:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key-here"
   ```

3. **Run the Application**:
   ```bash
   .venv/bin/streamlit run app.py
   ```

## Application Structure

- `app.py`: Streamlit frontend layout and simulated workflows.
- `agents.py`: LLM agent logic using `google-genai` SDK and structured outputs.
- `db.py`: SQLite database schema definition, seeding, and helper methods.
- `test_agents.py`: Mocked pytest suite verifying agent guardrails, validations, and idempotency.
- `venueflow_mock.db`: Local SQLite database.

## Tab Breakdown

1. **💍 Wedding Onboarding**: Runs the `intake_planner` agent. Validates if the couple's budget matches Irish market realities. If realistic, splits the budget and seeds a timeline.
2. **🗺️ Sourcing & Schedulers**: Runs `venue_matcher` and `supplier_matcher` agents. Shortlists up to 3 candidates, drafts email inquiries, and updates booking tables.
3. **✉️ Inbound Quotes**: Runs `quote_extractor`. Paste vendor emails to extract structured quotes. Compares totals against allocated budget lines to trigger `budget_monitor` alerts if exceeded.
4. **📊 Metrics Dashboard**: Summarizes weddings count, total agent decisions, blocked/guardrailed runs, and average LLM confidence scores.
5. **📜 Audit Logs & DB Explorer**: Inspects full inputs, outputs, rationales, API costs/latencies, and provides CSV logs download with PII redacted.

## Limitations & Architecture Warnings

- **Local Concurrency**: Backed by SQLite. Set to WAL mode, but multiple concurrent writes may serialize execution.
- **Mock Services**: Payments (Stripe), email parsing (SendGrid), and SMS reminders (Twilio) are simulated locally in code.
- **Mock Auth**: Auth states are tracked via sidebar selectors and `st.session_state` rather than Firebase Auth.
