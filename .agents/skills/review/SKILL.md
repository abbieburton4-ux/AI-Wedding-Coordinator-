---
name: review
description: Independent review of a code change (a diff, branch or set of files) against this repo's hard rules, agent contract, product scope and definition of done, reporting findings ranked by severity. Use before declaring any non-trivial change done, or when asked to review a branch or diff.
---

# Review

You're checking a change to an app a real couple will rely on. Review it as if you didn't write it, and look for what's wrong, not for reasons to approve. Read the diff and the surrounding code it touches. Review only: don't edit files or change git state. If you're also the author (for example in AI Studio, which can't delegate), do this as a separate pass and re-read the diff cold.

## Scope
Review the diff you were given. If none was given, review `git diff main...HEAD` plus uncommitted changes.

## Check, in this order

1. **Hard rules** in `.agents/AGENTS.md`:
   - no automatic send path;
   - no invented vendor facts, and indicative or simulated output labelled as such;
   - no real personal data in code, seeds, tests, logs or commit text;
   - no agent marking money or commitments done;
   - no secrets in git, `frontend/src/` or `VITE_*`;
   - no schema change on real data without a migration path;
   - no fabricated metrics or default confidence/latency/token values;
   - nothing shared or irreplaceable kept only in `localStorage`;
   - no weakened test or silenced type error;
   - no unexplained new dependency.
2. **Agent contract** (`agent-features` skill): server-side calls, log row first and mutation last, structured output, guardrails before saving, honest fallback, minimal log payloads, and a `verify_agents.py` case for the changed path.
3. **Product scope**: does the change match what was asked and what `docs/product/` says? Flag anything that changes product behaviour without a recorded decision, or that extends a legacy SaaS surface.
4. **Correctness and security**: logic errors, edge cases, unhandled errors (loading, empty, error states), input handling and validation, auth or route gaps, broken behaviour that used to work.
5. **Tests**: is new behaviour covered, and do the existing tests still make sense?
6. **Docs sync**, per the `finish-work` table. If a rule changed, `.agents/ai-studio-system-instructions.md` must still match `AGENTS.md`.
7. **Verification**: run the `verify` skill yourself, skipping its clean-up step. Don't trust a claim that it passed.
8. **Clarity**: dead code, misleading names, needless complexity. These are non-blocking.

## Report

List findings most severe first. For each one, give:

- **Severity**: `blocking` (violates a hard rule, fails verification, or breaks behaviour) or `non-blocking`
- **Location**: `file:line`
- **Issue**: one sentence
- **Failure scenario**: concrete input or state, and what goes wrong

Then list what you verified (commands and exit codes) and what you couldn't. If nothing blocks the change, say so plainly.
