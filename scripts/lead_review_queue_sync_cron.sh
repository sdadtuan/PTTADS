#!/usr/bin/env bash
# Cron: sync B2 review queue (FR-CRM-04) via Nest internal key.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

BASE="${PTT_CRM_API_URL:-http://127.0.0.1:3000}"
KEY="${PTT_CRM_INTERNAL_KEY:-}"

if [[ -z "$KEY" ]]; then
  echo "lead_review_queue_sync: missing PTT_CRM_INTERNAL_KEY" >&2
  exit 1
fi

if [[ "${PTT_CRM_LEADS_FUNNEL_NEST:-0}" != "1" ]]; then
  echo "lead_review_queue_sync: funnel Nest disabled — skip"
  exit 0
fi

out="$(curl -sf -X POST "$BASE/api/v1/leads/review-queue/sync" \
  -H "X-PTT-Internal-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{}' || true)"

if [[ -z "$out" ]]; then
  echo "lead_review_queue_sync: POST failed" >&2
  exit 1
fi

echo "lead_review_queue_sync: $out"
