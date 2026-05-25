# AgentDecisionLog — Schema & CSV Export Template

Purpose: canonical schema for recording every autonomous agent action for auditability and submission. Exports must be human-readable, machine-parseable, and include named customer contact references for judges.

Storage assumptions
- Store as a DB table (Postgres recommended) with JSONB columns for payloads.
- Keep full audit history; do not overwrite rows.
- PII handling: redact or hash sensitive fields in export unless explicit consent is obtained.

Schema (Postgres types)

- id: UUID PRIMARY KEY
- agent_id: TEXT  -- identifier for the agent (eg. `planner-v1`)
- event_id: UUID NULLABLE REFERENCES event(id)
- booking_id: UUID NULLABLE REFERENCES booking(id)
- user_id: UUID NULLABLE REFERENCES "user"(id)  -- actor who triggered or received decision
- timestamp: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- decision_type: TEXT NOT NULL  -- e.g. `generate_quote`, `ask_deposit`, `reschedule`, `draft_contract`, `send_reminder`
- input_payload: JSONB NOT NULL  -- agent input context (enquiry text, parsed slots, user profile)
- output_payload: JSONB NOT NULL  -- agent output (quote object, actions taken, messages sent)
- confidence_score: NUMERIC(5,4) NULLABLE  -- 0.0000..1.0000
- external_api_calls: JSONB NULLABLE  -- list of outgoing API calls made (service, endpoint, status)
- follow_up_actions: JSONB NULLABLE  -- scheduled or triggered follow-ups (agent tasks)
- request_id: TEXT NULLABLE  -- tracing id for correlating logs across services
- latency_ms: INTEGER NULLABLE  -- round-trip time for the decision in milliseconds
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

Indexes & constraints
- INDEX on (event_id), (booking_id), (user_id), (agent_id), (timestamp DESC)
- CONSTRAINT ensure `decision_type` is from a known enum set (validate in app)

Implementation notes
- Keep `input_payload` and `output_payload` compact: include the minimal context needed to explain the decision. Example keys: `user_message`, `parsed_slots`, `pricing_factors`, `selected_line_items`, `rationale`.
- `rationale` should be a short human-readable string in `output_payload.rationale` explaining *why* the agent chose that action.
- Record all external writes (Stripe charge id, contract url, calendar event id) in `external_api_calls` for verifiability.
- If a decision involves money, include `output_payload.amount` and `output_payload.currency`.

CSV Export requirements
- Encoding: UTF-8
- Newline: LF
- Delimiter: comma
- All fields must be quoted with double quotes `"`.
- JSON fields must be valid JSON strings and JSON-escaped inside the CSV cell.
- Timestamp format: ISO 8601 (RFC3339) with timezone, e.g. `2026-05-24T14:32:10+01:00`.
- File name pattern: `agent_decision_log_EXPORT_YYYYMMDDTHHMMSS.csv`

CSV column order (header)

id,agent_id,event_id,booking_id,user_id,timestamp,decision_type,input_payload,output_payload,confidence_score,external_api_calls,follow_up_actions,request_id,latency_ms,created_at

Description of columns
- id: UUID of the log row
- agent_id: logical agent name/version
- event_id: linked event (if any)
- booking_id: linked booking (if any)
- user_id: user involved (couple/planner/venue_admin)
- timestamp: when the decision was logged (ISO 8601)
- decision_type: short enum describing the decision
- input_payload: JSON string with the agent's input context
- output_payload: JSON string with the agent's outputs and `rationale`
- confidence_score: numeric 0..1
- external_api_calls: JSON array of calls made and their results
- follow_up_actions: JSON array of scheduled actions
- request_id: trace id
- latency_ms: decision latency
- created_at: row creation timestamp

CSV example (single header + one example row)

"id","agent_id","event_id","booking_id","user_id","timestamp","decision_type","input_payload","output_payload","confidence_score","external_api_calls","follow_up_actions","request_id","latency_ms","created_at"

"8b2f1a6e-4c9f-4b3a-9f0d-12a3b456cdef","planner-v1","d4a9a9e4-1234-4d5b-9c8e-abcdef012345","6f7b8c9d-2345-4e6f-9a0b-abcdef678901","a12b34c5-6789-4d0e-9abc-0123456789ab","2026-05-24T13:02:10+01:00","generate_quote","{""user_message"":""Hi, we want June 18th for 120 guests"",""parsed_slots"":{""date"":""2026-06-18"",""guests"":120}}","{""quote_id"":""q_20260524_0001"",""line_items"": [{""item"":""Venue hire"",""amount"":2500}],""total_amount"":2500,""currency"":""EUR"",""rationale"":""Used peak-season pricing + 120 guests""}","0.9400","[{""service"":""stripe"",""endpoint"":""/charges"",""status"":""skipped""}]","[]","req-9f8e7d6c","235","2026-05-24T13:02:11+01:00"

Export tooling notes
- Implement a server-side export endpoint `GET /admin/exports/agent-decision-log?from=...&to=...` that streams the CSV to avoid memory pressure.
- Ensure exported files include a minimal `manifest.json` (optional) summarizing counts and time range.

Submission checklist items derived from logs
- CSV export covering the submission window (Day 1..Day 90) with non-redacted named customer contacts (or a separate contact list CSV with consent).
- Screenshots of the dashboard showing live agent decisions (timestamped).
- CSV of revenue (Stripe receipts) mapped to booking_id/contract_id.

Retention & security
- Retention policy: keep full logs for at least 1 year; for submission, keep a copy of the submission window permanently.
- Access control: restrict exports to founder + admin; log export actions as well.


