#!/usr/bin/env bash
# EM-6 gate — Send Platform (prepare → send_queue → send_batch → webhook ingest)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
export PTT_WEBHOOK_V1_ENQUEUE="${PTT_WEBHOOK_V1_ENQUEUE:-1}"
export PTT_EMAIL_SEND_ENABLED="${PTT_EMAIL_SEND_ENABLED:-1}"
export PTT_EMAIL_ESP_DRY_RUN="${PTT_EMAIL_ESP_DRY_RUN:-1}"
export PTT_EMAIL_WEBHOOK_VERIFY="${PTT_EMAIL_WEBHOOK_VERIFY:-0}"
export PTT_WEBHOOKS_NEST_EMAIL="${PTT_WEBHOOKS_NEST_EMAIL:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-approver@demo.local:demo123:00000000-0000-0000-0000-000000000001:approver}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase6-email-send-platform-report.json"

echo "==> EM-6 unit tests"
"$PYTHON" -m pytest "$ROOT/tests/test_email_mkt_em6.py" -q

echo ""
echo "==> Ensure EM DDL"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em3.sh"

GATE_OK=true
NOTES=()

if [[ "${SKIP_NEST_SMOKE:-0}" == "1" ]]; then
  echo "SKIP  Nest smoke"
else
  STAFF_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"staff@demo.local","password":"demo123"}' \
    | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')
  [[ -n "$STAFF_TOKEN" ]] || { echo "FAIL staff login" >&2; GATE_OK=false; NOTES+=("staff_login_failed"); }

  if [[ -n "${STAFF_TOKEN:-}" ]]; then
    CLIENT_ID=$("$PYTHON" - <<'PY'
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT id::text FROM clients ORDER BY created_at ASC LIMIT 1")
row = cur.fetchone()
cur.close()
conn.close()
print(row[0] if row else "")
PY
)
    if [[ -z "$CLIENT_ID" ]]; then
      echo "WARN  no clients — skip send flow smoke"
    else
      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/workspaces" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-6 Gate Workspace\",\"default_from_email\":\"noreply@example.com\"}" 2>/dev/null || true

      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/contacts/import" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"rows\":[{\"email\":\"em6-gate@example.com\",\"lifecycle_stage\":\"subscriber\"}]}" >/dev/null

      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/consent" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"email\":\"em6-gate@example.com\",\"status\":\"opted_in\",\"source\":\"em6-gate\"}" >/dev/null

      SEG_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-6 Gate Segment\",\"definition_json\":{\"lifecycle_stage\":\"subscriber\"}}")
      SEG_ID=$(echo "$SEG_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')
      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments/${SEG_ID}/compute" \
        -H "Authorization: Bearer $STAFF_TOKEN" -d '{}' >/dev/null

      TMPL_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/templates" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-6 Gate Template\",\"subject_template\":\"Hello EM-6\",\"html_body\":\"<p>Hi</p><a href=\\\"{{unsubscribe_url}}\\\">Unsubscribe</a>\"}")
      TMPL_ID=$(echo "$TMPL_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')

      CAMP_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-6 Gate Campaign\",\"template_id\":\"$TMPL_ID\",\"segment_id\":\"$SEG_ID\"}")
      CAMP_ID=$(echo "$CAMP_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')

      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns/${CAMP_ID}/submit" \
        -H "Authorization: Bearer $STAFF_TOKEN" -d '{}' >/dev/null
      echo "OK  submit → pending_approval"

      APPROVE_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns/${CAMP_ID}/approve" \
        -H "Authorization: Bearer $STAFF_TOKEN" -d '{}')
      echo "$APPROVE_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="approved"; print("OK  staff approve")'

      echo "==> Run worker once (prepare + send_batch jobs)"
      (cd "$ROOT" && "$PYTHON" -m ptt_worker --once) || true
      sleep 1
      (cd "$ROOT" && "$PYTHON" -m ptt_worker --once) || true

      SENT_COUNT=$("$PYTHON" - <<PY
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM email_mkt.send_queue WHERE campaign_id = %s::uuid AND status = 'sent'", ("$CAMP_ID",))
print(cur.fetchone()[0])
cur.close()
conn.close()
PY
)
      if [[ "$SENT_COUNT" -ge 1 ]]; then
        echo "OK  send_queue sent count=$SENT_COUNT"
      else
        echo "FAIL  expected send_queue sent rows" >&2
        GATE_OK=false
        NOTES+=("send_queue_empty")
      fi

      SEND_ID=$("$PYTHON" - <<PY
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT id::text FROM email_mkt.send_queue WHERE campaign_id = %s::uuid LIMIT 1", ("$CAMP_ID",))
row = cur.fetchone()
cur.close()
conn.close()
print(row[0] if row else "")
PY
)

      WEBHOOK_BODY="[{\"event\":\"open\",\"email\":\"em6-gate@example.com\",\"timestamp\":1,\"custom_args\":{\"send_id\":\"$SEND_ID\"}}]"
      curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/webhooks/email" \
        -H 'Content-Type: application/json' \
        -H "X-PTT-Client-Id: $CLIENT_ID" \
        -d "$WEBHOOK_BODY" \
        | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("verified") is True; print("OK  POST /webhooks/email")'

      (cd "$ROOT" && "$PYTHON" -m ptt_worker --once) || true

      OPEN_COUNT=$("$PYTHON" - <<PY
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM email_mkt.engagement_events WHERE send_id = %s::uuid AND event_type = 'open'", ("$SEND_ID",))
print(cur.fetchone()[0])
cur.close()
conn.close()
PY
)
      if [[ "$OPEN_COUNT" -ge 1 ]]; then
        echo "OK  engagement_events open count=$OPEN_COUNT"
      else
        echo "FAIL  engagement ingest" >&2
        GATE_OK=false
        NOTES+=("engagement_missing")
      fi
    fi
  fi
fi

"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = {
    "phase": "em-6",
    "component": "email_send_platform",
    "ok": $( [[ "$GATE_OK" == true ]] && echo "True" || echo "False" ),
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "job_types": ["email_campaign_prepare", "email_send_batch", "email_engagement_ingest"],
    "webhook": "POST /api/v1/webhooks/email",
}
path = Path("$REPORT")
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

if [[ "$GATE_OK" != true ]]; then
  exit 1
fi
echo "EM-6 gate PASS"
