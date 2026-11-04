---
name: verify
description: Run this repo's verification gate (backend verify scripts + frontend production build) and interpret the result. Use before claiming any code change works, before committing, and when asked to "test" or "check" the app.
---

# Verify

There's no second human reviewer and no CI on PRs yet (backlog B15), so this gate is the safety net. Run every part that the change could affect; when in doubt, run all of it.

## Backend (from `backend/`)

1. If `.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. On Apple Silicon also `pip install greenlet` into the venv only (B16); don't add it to `requirements.txt` without the owner's go-ahead.
2. Run each script and record its exit code:
   ```bash
   GEMINI_API_KEY=dummy .venv/bin/python verify_endpoints.py
   GEMINI_API_KEY=dummy .venv/bin/python verify_agents.py
   GEMINI_API_KEY=dummy .venv/bin/python verify.py
   ```
   Each must exit 0 and print its success line.
3. If you changed agent behaviour, `verify_agents.py` must cover the new path. Add a test; never loosen an existing one.

## Frontend (from `frontend/`)

4. Run `npm ci` if `node_modules` is missing or `package-lock.json` changed.
5. Run `npm run build`. It must exit 0. Chunk-size warnings are fine. This is the only compile check; there is no typecheck script.
6. If you changed UI behaviour, run `npm run dev` against a local backend, exercise the affected route, and describe what you checked. The build doesn't catch logic errors.

## Clean up

7. **If you're reviewing someone else's change, skip this step**: list the files verification changed and leave them for the author. Otherwise: the backend scripts rewrite the tracked `backend/endpoints_test.db*` files (B17). Run `git restore backend/endpoints_test.db backend/endpoints_test.db-shm backend/endpoints_test.db-wal`, delete any new `backend/*_test.db-shm`/`-wal` files, then check `git status --short` shows only your intended changes.

## On failure

- Read the first error, not the last line.
- If a test or type error looks like a spec problem, don't silence it (`any`, `@ts-ignore`, a weakened assert). Report it.
- If it also fails on `main`, say so: it's pre-existing, not yours, but still worth a backlog entry.

## Report

State which steps ran and their exit codes. Name anything you couldn't run as `[BLOCKED]`. Never report "verified" for a step that didn't run.
