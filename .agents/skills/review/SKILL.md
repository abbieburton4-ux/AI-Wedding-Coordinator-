---
name: review
description: Review a code change (a diff, branch or set of files) for correctness bugs, regressions, missing tests and conflicts with the product doc, and report findings ranked by severity. Use before declaring any non-trivial change done.
---

# Review

> **Stub.** Tighten the checklist as the codebase grows.

Review the change as if you didn't write it. Read the diff and the surrounding code it touches.

## Check

1. **Correctness**: logic errors, edge cases, unhandled errors, broken behavior that used to work.
2. **Scope**: does the change match what was asked and what `docs/product/wedding.md` says? Flag anything that changes product behavior without a recorded decision.
3. **Tests**: is new behavior covered, and do the existing tests still make sense?
4. **Security and data**: guest and couple personal data, secrets, and input handling.
5. **Clarity**: dead code, misleading names, needless complexity. These are non-blocking.

## Report

List findings most severe first. For each one, give:

- **Severity**: `blocking` or `non-blocking`
- **Location**: `file:line`
- **Issue**: one sentence
- **Failure scenario**: concrete input or state, and what goes wrong

If nothing blocks the change, say so plainly. Don't edit files; only report.
