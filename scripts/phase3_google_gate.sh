#!/usr/bin/env bash
# Phase 3 Google Ads adapter gate (G1–G4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export GOOGLE_PILOT_CLIENT_ID="${GOOGLE_PILOT_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PTT_GOOGLE_INSIGHTS_SYNC="${PTT_GOOGLE_INSIGHTS_SYNC:-1}"
export PTT_GOOGLE_INSIGHTS_STUB="${PTT_GOOGLE_INSIGHTS_STUB:-1}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export PTT_TOKEN_VAULT_KEY="${PTT_TOKEN_VAULT_KEY:-test-vault-key-for-unit-tests-only}"
export PORTAL_E2E_APPROVER_EMAIL="${PORTAL_E2E_APPROVER_EMAIL:-approver@demo.local}"
export PORTAL_E2E_APPROVER_PASSWORD="${PORTAL_E2E_APPROVER_PASSWORD:-demo123}"
cd "$ROOT"

echo "==> Apply Google sync DDL"
./scripts/apply_pg_ddl_v3_google_sync.sh

echo "==> Seed Google pilot client (channel + hub map + stub sync)"
"$PYTHON" scripts/seed_google_pilot_client.py

echo "==> Google adapter gate pack"
"$PYTHON" -m ptt_crm.phase3_google_gates
