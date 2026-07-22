#!/usr/bin/env bash
# Activate a test client and verify ClientOnboarded + meta_insights_sync in PostgreSQL.
#
# Usage (on VPS, from /var/www/ptt):
#   set -a && source .env && set +a
#   ADMIN_PASSWORD='...' CLIENT_ID=333a8341-a08f-4b7e-9ddf-b7c053935d03 ./scripts/wave_b2_activate_verify.sh
#
# Optional:
#   FORCE=1          — POST .../activate?force=1 (skip checklist gate)
#   BASE=http://127.0.0.1:3000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
CLIENT_ID="${CLIENT_ID:-}"
FORCE="${FORCE:-0}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD (from .env)" >&2
  exit 1
fi
if [[ -z "$CLIENT_ID" ]]; then
  echo "Set CLIENT_ID (test agency client UUID)" >&2
  exit 1
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -f "$ROOT/.env" ]]; then
    set -a && source "$ROOT/.env" && set +a
  fi
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL required (source .env first)" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }
warn() { echo "WARN $*"; }

echo "== Wave B2 activate verify =="
echo "BASE=$BASE CLIENT_ID=$CLIENT_ID FORCE=$FORCE"
echo "PTT_JOBS_ENABLED=${PTT_JOBS_ENABLED:-unset}"
echo ""

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
if [[ -z "$TOKEN" ]]; then
  echo "FAIL login" >&2
  exit 1
fi
ok "staff login"

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

BEFORE="$(mktemp)"
curl -sf "$BASE/api/v1/clients/$CLIENT_ID" "${AUTH[@]}" >"$BEFORE"
python3 - <<'PY' "$BEFORE"
import json, sys
d = json.load(open(sys.argv[1]))
print(f"Before: status={d.get('status')} code={d.get('code')} name={d.get('name')}")
PY

OB="$(mktemp)"
curl -sf "$BASE/api/v1/clients/$CLIENT_ID/onboarding" "${AUTH[@]}" >"$OB"
python3 - <<'PY' "$OB"
import json, sys
d = json.load(open(sys.argv[1]))
p = d.get("progress") or {}
print(f"Checklist: {p.get('completed', '?')}/{p.get('total', '?')} ({p.get('percent', '?')}%)")
PY
rm -f "$OB"

ACTIVATE_URL="$BASE/api/v1/clients/$CLIENT_ID/activate"
if [[ "$FORCE" == "1" ]]; then
  ACTIVATE_URL="${ACTIVATE_URL}?force=1"
fi

RESP="$(mktemp)"
HTTP="$(curl -s -o "$RESP" -w "%{http_code}" -X POST "$ACTIVATE_URL" "${AUTH[@]}" -d '{}')"
if [[ ! "$HTTP" =~ ^2 ]]; then
  if [[ "$HTTP" == "400" && "$FORCE" != "1" ]]; then
    warn "activate HTTP 400 — retry with FORCE=1 if checklist incomplete"
  fi
  bad "POST activate (HTTP $HTTP): $(head -c 300 "$RESP" | tr '\n' ' ')"
  rm -f "$RESP" "$BEFORE"
  exit 1
fi
ok "POST activate (HTTP $HTTP)"

python3 - <<'PY' "$RESP"
import json, sys
d = json.load(open(sys.argv[1]))
fx = d.get("side_effects") or {}
jobs = fx.get("jobs_enqueued") or []
print(f"After: status={d.get('status')}")
print(f"side_effects.domain_event_id={fx.get('domain_event_id')!r}")
print(f"side_effects.workflow_signal={fx.get('workflow_signal')!r}")
print(f"jobs_enqueued: {len(jobs)}")
for j in jobs:
    created = j.get("created")
    print(f"  - {j.get('job_type')} id={j.get('id')} status={j.get('status')} created={created}")
if not fx.get("domain_event_id"):
    print("WARN API returned null domain_event_id")
if not jobs:
    print("WARN no jobs_enqueued — check PTT_JOBS_ENABLED=1")
PY

EVENT_ID="$(python3 -c "import json; d=json.load(open('$RESP')); print((d.get('side_effects') or {}).get('domain_event_id') or '')")"
JOB_ID="$(python3 -c "import json; d=json.load(open('$RESP')); js=(d.get('side_effects') or {}).get('jobs_enqueued') or []; print(js[0]['id'] if js else '')")"
rm -f "$RESP" "$BEFORE"

echo ""
echo "-- PostgreSQL domain_events --"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "
SELECT id::text, event_type, aggregate_id, payload->>'client_code' AS client_code, created_at
FROM domain_events
WHERE event_type = 'ClientOnboarded' AND aggregate_id = '$CLIENT_ID'
ORDER BY created_at DESC
LIMIT 5;
"

if [[ -n "$EVENT_ID" ]]; then
  ROW="$(psql "$DATABASE_URL" -tA -c "SELECT COUNT(*) FROM domain_events WHERE id = '$EVENT_ID'::uuid")"
  [[ "$ROW" == "1" ]] && ok "domain_events row id=$EVENT_ID" || bad "domain_events missing id=$EVENT_ID"
else
  COUNT="$(psql "$DATABASE_URL" -tA -c "
    SELECT COUNT(*) FROM domain_events
    WHERE event_type = 'ClientOnboarded' AND aggregate_id = '$CLIENT_ID'
      AND created_at > NOW() - INTERVAL '5 minutes'
  ")"
  [[ "$COUNT" -ge 1 ]] && ok "ClientOnboarded in last 5m (count=$COUNT)" || bad "no recent ClientOnboarded for client"
fi

echo ""
echo "-- PostgreSQL job_queue (meta_insights_sync) --"
TODAY="$(date -u +%Y-%m-%d)"
IDEM="meta_insights_sync:${CLIENT_ID}:${TODAY}"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "
SELECT id::text, job_type, status, idempotency_key, created_at
FROM job_queue
WHERE client_id = '$CLIENT_ID'::uuid AND job_type = 'meta_insights_sync'
ORDER BY created_at DESC
LIMIT 5;
"

IDEM_ROW="$(psql "$DATABASE_URL" -tA -c "SELECT id::text FROM job_queue WHERE idempotency_key = '$IDEM' LIMIT 1")"
if [[ -n "$IDEM_ROW" ]]; then
  ok "job_queue idempotency_key=$IDEM id=$IDEM_ROW"
else
  bad "job_queue missing idempotency_key=$IDEM (PTT_JOBS_ENABLED?)"
fi

if [[ -n "$JOB_ID" ]]; then
  JROW="$(psql "$DATABASE_URL" -tA -c "SELECT status FROM job_queue WHERE id = '$JOB_ID'::uuid")"
  [[ -n "$JROW" ]] && ok "API job id=$JOB_ID status=$JROW" || bad "API job id=$JOB_ID not in DB"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B2 activate verify PASSED"
  exit 0
fi
echo "Wave B2 activate verify FAILED"
exit 1
