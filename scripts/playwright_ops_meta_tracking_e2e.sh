#!/usr/bin/env bash
# Playwright E2E-M4 — ops-web /meta/tracking (requires Nest + ops-web running)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export OPS_E2E_URL="${OPS_E2E_URL:-http://127.0.0.1:3200}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export OPS_E2E_SKIP_SERVER="${OPS_E2E_SKIP_SERVER:-1}"
export OPS_E2E_STAFF_EMAIL="${OPS_E2E_STAFF_EMAIL:-staff@demo.local}"
export OPS_E2E_STAFF_PASSWORD="${OPS_E2E_STAFF_PASSWORD:-demo123}"
export NEXT_PUBLIC_PTT_META_TRACKING_ENABLED="${NEXT_PUBLIC_PTT_META_TRACKING_ENABLED:-1}"

cd "$ROOT/services/ops-web"
if [[ ! -d node_modules/@playwright/test ]]; then
  npm install
fi
if [[ ! -d ~/.cache/ms-playwright ]] && [[ ! -d node_modules/playwright/.local-browsers ]]; then
  npx playwright install chromium
fi
npm run test:e2e -- e2e/meta-tracking.spec.ts
