---
name: agent-features
description: Contract for any Gemini agent in this app (intake planner, venue/supplier matchers, quote extractor, concierge, budget monitor) — the run_agent decision-log contract, structured output, guardrails, honest metrics and fallbacks. Use when adding, changing or reviewing an agent or anything that shows agent output.
---

# Agent features

Agents live in `backend/app/agents/` and run behind the `run_agent` decorator in `orchestrator.py`. The couple may treat their output as advice, so honesty matters more than polish. Read `docs/architecture.md` and `docs/agent-decision-log.md` before changing one.

## The contract

1. **Server-side only.** Gemini is called from the backend with the key from backend config. Never from `frontend/`, never via a `VITE_*` variable.
2. **Log row first, domain mutation last.** `run_agent` writes the `AgentDecisionLog` row and runs the agent inside a savepoint; the agent changes domain tables only after its guardrails pass.
3. **Structured output.** Request a `response_schema` (Pydantic model with descriptive `Field` docs) and read the JSON. Never parse free text into data. The schema isn't validated after `json.loads`, so treat every field as possibly missing.
4. **Guardrails before showing or saving:**
   - categories come from the allowed list in `utils/constants.py`;
   - recommended vendors must exist in the catalogue (no hallucinated ids);
   - budgets must be realistic for the region and guest count.

   On a guardrail failure, save nothing as a recommendation, return `status: "blocked"` with an `error_kind`, and let the log record `blocked_by_guardrail`.
5. **Honest metrics.** Latency is measured by the orchestrator. Confidence and token counts come from the model's response; if it doesn't supply them, record `None`, never a default (AGENTS.md rule 10).
6. **Minimal payloads.** Log IDs and the minimum context the decision needs: no guest lists, contact details or health notes.
7. **Drafts, never sends.** An agent may draft an inquiry or message, as text the couple sends themselves (rule 1). There is no send path today. Any future send path needs a human click per message, and a stop-and-ask first. The `resolve_inquiry_recipient` routing that `seed_data_real.py`'s docstring mentions doesn't exist (B20); don't rely on it.
8. **Honest fallback.** If the call fails, the log row says `error` and the UI says it failed. Never show a canned or mock answer as if it were real; label any sample output as sample.
9. **No commitments.** Agents never mark payments paid, bookings confirmed or contracts accepted (rule 4); a matcher may only create `shortlisted` bookings.

## Tests

Every agent path (success, each guardrail, missing optional fields) is covered in `backend/verify_agents.py` with a mocked Gemini client. Add a case for the path you changed; never weaken an existing assert.

## Done
Run `verify`. Update "What's actually there today" in `.agents/AGENTS.md` if what's real changed.
