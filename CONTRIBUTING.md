# Contributing to VenueFlow

This is a 2-founder hackathon project on a hard deadline (17 Aug 2026). Keep PRs small, commits boring, and surprises small.

---

## Repository Layout

| Path | Purpose |
|---|---|
| [backend/](backend/) | FastAPI backend, database schemas (SQLModel), agent implementations, migrations, and test scripts. |
| [frontend/](frontend/) | Vite + React 18 frontend (Landing + Experience + Wedding Views). |
| [docs/](docs/) | Architecture, ERD, runway, strategic memo, agent decision log spec. |
| [scripts/](scripts/) | One-off scripts (e.g., `build_tracker.py` regenerates `runway-tracker.xlsx`) |
| `runway-tracker.xlsx` | Live execution tracker. Edit in Excel/Numbers/Sheets; commit changes when status moves. |

---

## Local Development

### Backend (FastAPI + Worker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # macOS/Linux  (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
export GEMINI_API_KEY=AIza...       # required for live agent runs (must be a Developer key, starts with AIza)
export WORKER_BASE_URL=http://localhost:8000   # non-Docker: loop async agent tasks back to this process
uvicorn app.main:app --reload      # opens http://localhost:8000
```

The server automatically initializes and seeds the SQLite database (`endpoints_test.db` or configured local db) on startup if it does not exist.

> **Non-Docker gotcha:** agent work runs via Cloud Tasks → a separate worker. Outside
> Docker there's no `worker` host, so `WORKER_BASE_URL` **must** point at this same
> process (`http://localhost:8000`) or the emulator/worker fallback silently drops the
> task — the symptom is a wedding stuck in `planning`/`preview` with an empty plan.
> (Docker Compose wires the real worker, so this is only for a bare `uvicorn` run.)

> **Payment gate affects local behavior:** with `REQUIRE_PAYMENT=True` (default) a fresh
> intake runs the planner for free and lands in `preview` (a teaser — partial budget +
> timeline, locked vendors); the paid venue/supplier cascade only runs after checkout
> (`PAYMENTS_PROVIDER=mock` = no real charge). Set `REQUIRE_PAYMENT=False` to get the
> full plan immediately on intake (handy for quick local testing).

> **⚠️ Gemini free-tier quota = 20 requests/day (Flash).** One couple's full flow
> (intake_planner + the 4-agent matcher cascade + a few Concierge questions + quote
> extractions) easily exceeds that, so the agents will start returning `429
> RESOURCE_EXHAUSTED` — both in the app and in batch scripts like
> `generate_demo_vendors.py`. **Use a paid Gemini key for real demos / data generation.**
> Also note: the free tier has **0 quota for `gemini-2.5-pro`**, which is why agents
> default to Flash (`GEMINI_PLANNING_MODEL` / `GEMINI_FAST_MODEL` in `agents/base.py`).

### Frontend (Vite + React)

```bash
cd frontend
npm i
npm run dev                          # vite dev server on http://localhost:5173
npm run build                        # production build to dist/
```

By default, the React frontend connects to `http://localhost:8000`. You can configure this via the `VITE_API_URL` env variable or toggle backend integration in `frontend/src/app/api/config.ts`.

### Tests

```bash
cd backend
source .venv/bin/activate
python verify_endpoints.py    # Verify FastAPI REST endpoints and security
python verify_agents.py       # Verify agent tasks, schemas, and guardrails
```

Tests use temporary databases and mocked API calls to Gemini where appropriate, meaning they run quickly and without consuming API quotas.

---

## How to Add a New Agent

Agents live in the [backend/app/agents/](backend/app/agents/) directory (e.g., `planner.py`, `matcher.py`, `extractor.py`). The shape:

1. **Define a Pydantic schema** for the structured output. Keep field descriptions verbose — Gemini uses them for tool calling / structured generation.
2. **Pick a model.** Add the agent name to `model_for()` in [backend/app/agents/base.py](backend/app/agents/base.py) if it's a reasoning task (→ `gemini-2.5-pro`); leave it as default (→ `gemini-2.5-flash`) for extraction/drafting.
3. **Open a log row first, mutate domain last.** Every agent function should follow this sequence:
   - Insert an `AgentDecisionLog` row with `status='pending'`
   - Call Gemini with the schema and system instructions
   - Validate output and apply guardrails (e.g., category whitelisting, hallucination checking)
   - On success: Write domain mutations and flip log to `status='success'` in one transaction
   - On guardrail block: Write `status='blocked_by_guardrail'` with an `error_kind`
   - On exception: Roll back changes and write `status='error'` with `error_kind`
4. **Capture metrics.** Capture `latency_ms`, `tokens_input`, `tokens_output`, `external_api_calls` JSON, and `confidence_score` — every row needs these for the submission CSV.
5. **Wire `parent_decision_id`** when the agent is triggered by another agent's output (e.g., `quote_extractor` -> parent is the matching `inquiry_draft`).
6. **Add verification coverage.** Add mock-based assertions in `verify_agents.py` to test the new agent's behavior and guardrail compliance.

---

## Agent & data behaviors worth knowing

- **Timeline is fitted to the runway.** `intake_planner` seeds milestones from the
  agent's `months_before` values, but `planner.py` then **compresses the plan into
  `[today, wedding_date]`** when the longest lead exceeds the days remaining, and floors
  every due date at today. Without this, a couple starting (say) 7 months before a
  December wedding got tasks dated 1–2 years in the past. Existing weddings need a
  **re-plan** (`POST /weddings/{id}/replan`) to pick up a changed timeline.
- **Adding vendors (Option A — VenueFlow is a coordinator tool, vendors don't "sign up").**
  The vendor catalog is reference data the matcher recommends from. Two ways to grow it
  (both at `backend/`):
  - `python load_vendors_csv.py` — bulk-load **real** vendors from `data/venues.csv` /
    `data/suppliers.csv` (idempotent; rows may carry a `source` column). Non-coders fill
    the spreadsheet from public directories.
  - `python generate_demo_vendors.py` — generate realistic **fictional** vendors via
    Gemini, tagged `source="demo_generated"` with no contact info. Demo/pitch only — keep
    them distinct from founder-verified real vendors; don't present them to judges/real couples.
  - Thin seed data = the matcher repeats the same 1–2 vendors. Keep ~5–6 per category per
    target region so it has room to differentiate.

## Code Style

- **Python:** PEP-8 with reasonable line length (~100 chars). No black/ruff config yet — keep formatting consistent within a file.
- **TypeScript:** match the surrounding file. No linter wired up and TypeScript isn't installed standalone, so use `npm run build` from `frontend/` as the compile check (Vite/esbuild strips types but catches syntax/import errors).
- **No comments** unless the *why* is non-obvious. Don't restate what the code does. Don't reference the current task or PR.
- **No new dependencies** without a 1-line justification in the commit message.
- **Never commit secrets.** `GEMINI_API_KEY`, Stripe keys, planner email lists — all out of repo. Use environment variables or `.env.local` (already `.gitignore`d). See [docs/secrets.md](docs/secrets.md) for the per-service runbook and [backend/.env.example](backend/.env.example) for the template to copy. A pre-commit `gitleaks` hook ships with the repo; install once with `brew install gitleaks pre-commit && pre-commit install` and it blocks accidental secrets at commit time. Do **not** disable it with `--no-verify`.

---

## Commits

- **Conventional Commits format:** `<type>(<scope>): <subject>`
  - `feat:` new functionality
  - `fix:` bug fix
  - `docs:` documentation only
  - `chore:` tooling, dependencies, no behavior change
  - `refactor:` code change with no behavior change
  - `test:` test-only changes
- **Imperative subject, ≤72 chars.** "add idempotency key" not "added idempotency key" or "adding idempotency key."
- **Body explains *why*, not *what*.** The diff shows what. Reserve prose for the reason.
- **One logical change per commit.** A PR can be multiple commits.
- **Sign off with Co-Authored-By when pairing with an LLM** for transparency in the submission audit trail.

Example:
```
feat(agents): wire parent_decision_id on quote_extractor

Closes the chain trace from intake → match → inquiry → quote so the
judge-facing decision graph renders end-to-end. Without this, the
quote_extract logs orphan from the matcher decisions.

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Branch + PR Workflow

- `main` is always deployable to GitHub Pages (frontend).
- Feature branches: `<owner>/<short-name>` — e.g., `alan/outreach-templates`, `atharva/timeline-builder`.
- **Merge via squash** for small features; merge commit for multi-commit refactors.
- **Do not push directly to `main`** during pilot week (the week of any milestone date — see `runway.md`). Open a PR and self-review.

### Large refactors split by subject

Refactors that touch >100 lines or >2 unrelated concerns should land as multiple commits, one per subject. The motivation is `git bisect`: if a regression turns up later, a single 273-line commit forces you to unpick it line-by-line; four 70-line commits each scoped to one agent (or one page, one table, one prompt) let `bisect` isolate the bad change in O(log n).

Concrete rule of thumb:

- One commit per agent function when refactoring the agent layer.
- One commit per page when refactoring the frontend.
- One commit per schema entity when changing the DB.
- Doc updates that accompany code changes go in the same commit (so the doc stays in sync at every history point).

If a refactor genuinely is atomic — moving a single function to a new module, renaming one constant everywhere — one commit is fine. The signal is "could a reviewer understand this in 5 minutes." If not, split.

---

## Docs Discipline

Docs in `docs/` are load-bearing for the submission. When you change code that contradicts a doc, **update the doc in the same PR.** Specifically:

- New agent → update [docs/architecture.md](docs/architecture.md) agent inventory + [docs/agent-decision-log.md](docs/agent-decision-log.md) decision_type vocabulary
- Schema change → update [docs/ERD.md](docs/ERD.md)
- Pivot or scope change → update [docs/strategic-memo.md](docs/strategic-memo.md) (add a dated addendum, don't rewrite history)
- Milestone shift → update [docs/runway.md](docs/runway.md) and re-run `scripts/build_tracker.py` to refresh `runway-tracker.xlsx`
- Known-but-unfixed gap → append to [docs/backlog.md](docs/backlog.md) with a B-number, location, why-deferred, and fix-shape. Also drop a `# TODO(name, YYYY-MM-DD):` at the code site for in-flight items. Friday review pass reconciles `grep -rn TODO` against the backlog.

---

## Submission-Safe Practices

Until 17 Aug 2026, every commit affects the submission. Specifically:

- **No secrets in history.** Run `git log -p --all | grep -i "api_key\|secret\|password\|stripe_sk"` before any force-push. Run [gitleaks](https://github.com/gitleaks/gitleaks) before submission.
- **No squashes that destroy decision trails.** A judge may want to read commit history as proof of execution discipline.
- **PII in test data only.** No real planner emails, real couple names, or real wedding dates in committed seed data or example logs.
- **Decision logs are exportable, not pretty.** Don't reformat the CSV at export time — keep it raw and machine-readable. The Submission Kit (`docs/submission/`) is where polished narratives live.

---

## Quick Reference

| Task | Command |
|---|---|
| Run Backend FastAPI | `cd backend && uvicorn app.main:app --reload` |
| Run Endpoint Tests | `cd backend && python verify_endpoints.py` |
| Run Agent Logic Tests | `cd backend && python verify_agents.py` |
| Run Frontend | `cd frontend && npm run dev` |
| Build Frontend | `cd frontend && npm run build` |
| Compile-check Frontend | `cd frontend && npm run build` (TypeScript isn't installed standalone, so `tsc` won't run; the Vite build is the compile check) |
| Regenerate Excel tracker | `python scripts/build_tracker.py` |

---

## When You're Stuck

1. Read [docs/runway.md](docs/runway.md) — is what you're doing on the critical path to 17 Aug?
2. Read [docs/architecture.md](docs/architecture.md) — is your change aligned with the agent invocation contract?
3. If neither, post in the founders' channel before you build it.
