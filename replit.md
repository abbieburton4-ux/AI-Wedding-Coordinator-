# VenueFlow on Replit

This import keeps its existing Python FastAPI backend and React/Vite frontend.
The owner requested a **demo preview first**, not real wedding access.

## Run

Use the **Start application** workflow, or `bash scripts/replit-demo.sh`.
The frontend listens on port 5000 and proxies `/api` to FastAPI on port 8000.
Open `/login` and select **Continue as a couple** to use the fictional seeded wedding.
Deep links work at the root path; the existing GitHub Pages build base is unchanged.

This workflow explicitly enables the app's existing `DEVELOPMENT_MODE` and
`ALLOW_MOCK_AUTH`. It uses the disposable, Git-ignored `backend/venueflow.db`
SQLite database. **Do not enter real guest details or other personal information,
and do not publish this demo configuration.** Real sign-in must be configured
separately, following `docs/setup-sign-in.md`, with development flags disabled.

## Dependencies

Replit manages Python dependencies through root `pyproject.toml` / `uv.lock`;
keep them aligned with `backend/requirements.txt`, the original backend list.
Restore Python packages with `uv sync --active` in Replit's managed environment.
Frontend dependencies remain in `frontend/package.json` and its lockfile:
`cd frontend && npm ci`.

The frontend overrides `websocket-driver` and `tar` to patched versions because
the imported lockfile versions were blocked by Replit's package security policy.
No framework or database migration was made.

## External services

- `GEMINI_API_KEY`: optional server-side Replit Secret for live AI planning,
  matching, extraction and concierge. Missing credentials cause explicit AI
  errors; seeded screens and non-AI operations work without it. Never use
  a `VITE_*` variable for this key.
- ElevenLabs voice needs `ELEVENLABS_API_KEY`; it is not configured for the demo.
- Firebase is intentionally not configured for this demo; sign-in is simulated.
- Docker, PostgreSQL and the Cloud Tasks emulator are not required. The existing
  development task dispatcher falls back to the same backend process as worker.

## Verify

From `backend/`, run `python verify_endpoints.py`, `python verify_agents.py`,
`python verify.py`, and `python verify_migrations.py`. These mock Gemini.
From `frontend/`, run `VITE_BASE=/ VITE_API_URL= npm run build`.
The backend scripts modify tracked test database files; restore only those
test artifacts afterwards. Do not delete or reset a user's application database.
