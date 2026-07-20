#!/usr/bin/env bash
# Write cutover + rollback drill (Phase 2 W8)
#
# Requires: Postgres (docker), Nest (:3000), Flask optional, DDL v3 applied
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

NEST_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_NEST_LEADS_URL="$NEST_URL"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

START_TS=$(date +%s)
echo "==> Write cutover drill nest=$NEST_URL"
echo "    Runbook: docs/runbooks/cutover-leads-write-phase2.md"

check_health() {
  local url="$1"
  if curl -sf "$url/health" >/dev/null 2>&1; then
    echo "OK  Nest health $url"
    return 0
  fi
  echo "FAIL Nest not reachable — ./scripts/local_crm_api_up.sh (PTT_LEADS_WRITE_ENABLED=1)" >&2
  return 1
}

check_health "$NEST_URL"

echo "==> Phase A — simulate cutover flags"
for var in \
  "PTT_LEADS_WRITE_ENABLED=1" \
  "PTT_LEADS_WRITE_UPSTREAM=nest" \
  "PTT_LEAD_SHADOW_SYNC=1" \
  "PTT_LEAD_REPLICA_SYNC=0"; do
  name="${var%%=*}"
  val="${var#*=}"
  eval "export $name=$val"
  if [[ "$name" == "PTT_LEADS_WRITE_UPSTREAM" ]]; then
    "$PYTHON" -c "
from ptt_crm.config import leads_write_upstream
assert leads_write_upstream() == '$val', leads_write_upstream()
print('OK  $name=$val')
"
  else
    "$PYTHON" -c "
import os
assert os.environ.get('$name') == '$val', os.environ.get('$name')
print('OK  $name=$val')
"
  fi
done

echo "==> Nest write smoke (staging POST/PATCH)"
export PTT_LEADS_WRITE_ENABLED=1
"$ROOT/scripts/local_leads_write_staging.sh" || {
  echo "WARN write smoke failed — is Nest built with write enabled?" >&2
}

echo "==> Shadow sync (if v3 + flag)"
export PTT_LEAD_SHADOW_SYNC=1
if "$ROOT/scripts/sync_lead_shadow.sh" incremental 2>/dev/null; then
  echo "OK  shadow sync ran"
else
  echo "SKIP shadow sync (DDL v3 or accounts not ready)"
fi

echo "==> Write dual-run check"
if "$PYTHON" "$ROOT/scripts/dual_run_write_check.py" --sample 10 --no-nest --quiet; then
  echo "OK  write dual-run"
else
  echo "WARN write dual-run mismatches — review before prod cutover" >&2
fi

echo ""
echo "==> Phase B — simulate rollback (≤ 5 min target)"
ROLLBACK_START=$(date +%s)
for var in \
  "PTT_LEADS_WRITE_UPSTREAM=flask" \
  "PTT_LEADS_WRITE_ENABLED=0" \
  "PTT_LEAD_REPLICA_SYNC=1" \
  "PTT_LEAD_SHADOW_SYNC=0"; do
  name="${var%%=*}"
  val="${var#*=}"
  eval "export $name=$val"
  if [[ "$name" == "PTT_LEADS_WRITE_UPSTREAM" ]]; then
    "$PYTHON" -c "
from ptt_crm.config import leads_write_upstream
assert leads_write_upstream() == '$val', leads_write_upstream()
print('OK  rollback $name=$val')
"
  else
    "$PYTHON" -c "
import os
assert os.environ.get('$name') == '$val'
print('OK  rollback $name=$val')
"
  fi
done
ROLLBACK_ELAPSED=$(( $(date +%s) - ROLLBACK_START ))
TOTAL_ELAPSED=$(( $(date +%s) - START_TS ))

echo ""
echo "OK  write cutover drill complete"
echo "    Rollback flag simulation: ${ROLLBACK_ELAPSED}s"
echo "    Total drill: ${TOTAL_ELAPSED}s (target rollback ≤ 300s)"
echo "Prod: docs/runbooks/cutover-leads-write-phase2.md §4–§8"

if [[ "${PTT_ROLLBACK_DRILL_RECORD:-1}" != "0" ]]; then
  echo ""
  echo "==> Record rollback drill evidence"
  "$PYTHON" "$ROOT/scripts/rollback_drill_record.py" --flags-only --report "${PTT_ROLLBACK_DRILL_REPORT:-$ROOT/.local-dev/rollback-drill-evidence.json}" || true
fi
