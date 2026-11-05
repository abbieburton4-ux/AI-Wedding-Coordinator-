#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../frontend"
export VITE_BASE=/
export VITE_API_URL=""
# Firebase's VITE_* web config is public by design. Private keys are never bundled.
npm ci
npm run build
