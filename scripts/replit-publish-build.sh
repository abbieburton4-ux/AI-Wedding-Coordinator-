#!/usr/bin/env bash
# Replit's publish build ([deployment] build in .replit). Replit applies its
# database changes to production only after this build succeeds, so refusing to
# build when the workspace database is behind the code stops a publish that would
# undo migrations in production (B86). Rebuilding the frontend in the workspace
# stays scripts/replit-build.sh, without this check.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python backend/publish_guard.py
exec bash scripts/replit-build.sh
