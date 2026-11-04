---
name: finish-work
description: Definition of done for any change in this repo — docs sync, commit hygiene and an honest report. Use before committing, opening a PR, or telling the user a task is finished.
---

# Finish work

## 1. Verify
Run the `verify` skill. If any step fails or didn't run, you're not done. Say so.

## 2. Sync docs in the same change

| You changed | Also update |
|---|---|
| An agent, its guardrails or what's real vs mocked | "What's actually there today" in `.agents/AGENTS.md`, and `docs/architecture.md` if the flow changed |
| The schema | `docs/ERD.md` (and stop first if real data exists: AGENTS.md rule 6) |
| Decision-log fields or statuses | `docs/agent-decision-log.md` |
| Commands, env vars, flags, ports | The Commands section of `.agents/AGENTS.md`, `RUNBOOK.md`, and `.agents/ai-studio-system-instructions.md` if it mentions them |
| A rule in `.agents/AGENTS.md` | The matching rule in `.agents/ai-studio-system-instructions.md` |
| A known gap you're leaving | A `docs/backlog.md` entry (B-number, where, why it matters, fix shape) |
| A backlog item you fixed | Move it to "Recently closed" with the fixing commit |
| Something that relies on a product decision | That decision must already be in `docs/product/decisions.md`. If it isn't, hand it to the product lane (`product-call`) or ask the owner; engineering doesn't edit `docs/product/` |

## 3. Commit
- Work on a branch and open a PR; never push to `main`. Stage files by name and check that `git diff --cached --name-only` lists only yours.
- Use Conventional Commits: an imperative subject of at most 72 characters and a body that explains *why*. Make one logical change per commit.
- Add a `Co-Authored-By:` trailer naming the agent.
- Before committing, check that no real guest, party or contact data and no keys are in the diff.

## 4. Report
Base it on `git show --stat`, not memory:
- what changed and why;
- the verification result, with exit codes;
- anything `[ASSUMPTION]`, `[GAP]` or `[BLOCKED]`;
- follow-ups you logged.

If code changed and the owner uses AI Studio, remind them to re-import the project from GitHub.
