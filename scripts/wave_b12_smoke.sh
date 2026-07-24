#!/usr/bin/env bash
# Wave B12 smoke — creative registry API (Nest must be running; flag=1; DDL v9 applied)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE="${PTT_CRM_API_BASE:-http://127.0.0.1:3001}"
TOKEN="${PTT_INTERNAL_API_KEY:-dev-internal-key}"

echo "== B12 smoke: GET /api/v1/meta/creative-links =="
curl -fsS -H "x-internal-key: ${TOKEN}" "${BASE}/api/v1/meta/creative-links?limit=1" | python3 -m json.tool

echo "OK: B12 smoke passed (disabled response acceptable when flag off)"
