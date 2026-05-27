# Contributing to VenueFlow

This is a 2-founder hackathon project on a hard deadline (17 Aug 2026). Keep PRs small, commits boring, and surprises small.

---

## Repository Layout

| Path | Purpose |
|---|---|
| [streamlit_mock/](streamlit_mock/) | Pilot app — Streamlit + SQLite + Gemini. This is where the agent layer lives. |
| [frontend/](frontend/) | Vite + React 18 marketing site, deployed to GitHub Pages |
| [docs/](docs/) | Architecture, ERD, runway, strategic memo, agent decision log spec |
| [scripts/](scripts/) | One-off scripts (e.g., `build_tracker.py` regenerates `runway-tracker.xlsx`) |
| `runway-tracker.xlsx` | Live execution tracker. Edit in Excel/Numbers/Sheets; commit changes when status moves. |

---

## Local Development

### Pilot app (`streamlit_mock/`)

```bash
cd streamlit_mock
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt
export GEMINI_API_KEY=...           # required for live agent runs
streamlit run app.py                 # opens http://localhost:8501
```

The first run seeds a local SQLite DB (`venueflow_mock.db`) with sample venues, suppliers, and two test weddings. The DB file is `.gitignore`d — never commit it.

### Marketing site (`frontend/`)

```bash
cd frontend
npm i
npm run dev                          # vite dev server
npm run build                        # production build to dist/
```

No backend dependency — this is a static marketing/landing site.

### Tests

```bash
cd streamlit_mock
.venv/bin/pytest test_agents.py -v
```

Tests are **fully mocked** — they don't call Gemini. The mock client returns canned JSON, so the suite is fast (<1s), free, and CI-safe.

---

## How to Add a New Agent

Agents live in [streamlit_mock/agents.py](streamlit_mock/agents.py). The shape:

1. **Define a Pydantic schema** for the structured output. Example: `IntakeResult`, `MatchingResult`. Keep field descriptions verbose — Gemini uses them.
2. **Pick a model.** Add the agent name to `model_for()` if it's a reasoning task (→ `gemini-2.5-pro`); leave it as default (→ `gemini-2.5-flash`) for extraction/drafting.
3. **Open a log row first, mutate domain last.** Every agent function:
   - inserts an `agent_decision_logs` row with `status='pending'`
   - calls Gemini with the schema and a system instruction
   - validates output, applies guardrails
   - on success: writes domain mutations + flips log to `status='success'` in **one** `conn.commit()`
   - on guardrail block: writes `status='blocked_by_guardrail'` with an `error_kind`
   - on exception: `conn.rollback()`, then writes `status='error'` with `error_kind='api_error'`
4. **Capture metrics.** `latency_ms`, `tokens_input`, `tokens_output`, `external_api_calls` JSON, `confidence_score` — every row needs these for the submission CSV.
5. **Wire `parent_decision_id`** when the agent is triggered by another agent's output (e.g., `quote_extractor` → parent is the matching `inquiry_draft`).
6. **Add a pytest case.** Mock the Gemini client; assert on the resulting DB state. See [test_agents.py](streamlit_mock/test_agents.py) for the pattern.

**Do not** copy the entire boilerplate scaffold across agents — extract shared logic into a helper as soon as you have 2 agents that look the same. (`run_agent(agent_id, decision_type, model, schema, system_prompt, mutate_fn)` is the right factor when we get there.)

---

## Code Style

- **Python:** PEP-8 with reasonable line length (~100 chars). No black/ruff config yet — keep formatting consistent within a file.
- **TypeScript:** match the surrounding file. No linter wired up; `tsc --noEmit` works from `frontend/`.
- **No comments** unless the *why* is non-obvious. Don't restate what the code does. Don't reference the current task or PR.
- **No new dependencies** without a 1-line justification in the commit message. The pilot app's transitive deps are already heavy.
- **Never commit secrets.** `GEMINI_API_KEY`, Stripe keys, planner email lists — all out of repo. Use environment variables or `.env.local` (already `.gitignore`d). See [docs/secrets.md](docs/secrets.md) for the per-service runbook and [streamlit_mock/.env.example](streamlit_mock/.env.example) for the template to copy. A pre-commit `gitleaks` hook ships with the repo; install once with `brew install gitleaks pre-commit && pre-commit install` and it blocks accidental secrets at commit time. Do **not** disable it with `--no-verify`.

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

- `main` is always deployable to GitHub Pages (frontend) and to the Streamlit Cloud pilot.
- Feature branches: `<owner>/<short-name>` — e.g., `alan/outreach-templates`, `atharva/timeline-builder`.
- **Merge via squash** for small features; merge commit for multi-commit refactors.
- **Do not push directly to `main`** during pilot week (the week of any milestone date — see `runway.md`). Open a PR and self-review.

### Large refactors split by subject

Refactors that touch >100 lines or >2 unrelated concerns should land as multiple commits, one per subject. The motivation is `git bisect`: if a regression turns up later, a single 273-line commit forces you to unpick it line-by-line; four 70-line commits each scoped to one agent (or one page, one table, one prompt) let `bisect` isolate the bad change in O(log n).

Concrete rule of thumb:

- One commit per agent function when refactoring the agent layer.
- One commit per UI tab when refactoring the Streamlit app.
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
| Run pilot app | `cd streamlit_mock && .venv/bin/streamlit run app.py` |
| Run tests | `cd streamlit_mock && .venv/bin/pytest test_agents.py -v` |
| Regenerate Excel tracker | `python scripts/build_tracker.py` |
| Build marketing site | `cd frontend && npm run build` |
| Type-check frontend | `cd frontend && npx tsc --noEmit` |
| Reset pilot DB | In the Streamlit sidebar: "Reset & Re-Seed Database" |

---

## When You're Stuck

1. Read [docs/runway.md](docs/runway.md) — is what you're doing on the critical path to 17 Aug?
2. Read [docs/architecture.md](docs/architecture.md) — is your change aligned with the agent invocation contract?
3. If neither, post in the founders' channel before you build it.
