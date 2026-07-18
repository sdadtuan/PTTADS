#!/usr/bin/env bash
# Staging pilot — write cutover pre-flight + smoke + gates (Phase 2 P0 #3)
#
# Requires: Postgres, Nest (:3000) with PTT_LEADS_WRITE_ENABLED=1, DDL v3
#
# Usage:
#   set -a && source deploy/env.staging-write-pilot.example && set +a
#   ./scripts/local_crm_api_up.sh                   # terminal 1
#   ./scripts/staging_write_cutover_pilot.sh
#   ./scripts/staging_write_cutover_pilot.sh --apply-sync-mode --drill
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_LEADS_WRITE_ENABLED="${PTT_LEADS_WRITE_ENABLED:-1}"
export PTT_LEADS_WRITE_UPSTREAM="${PTT_LEADS_WRITE_UPSTREAM:-nest}"
export PTT_LEAD_SHADOW_SYNC="${PTT_LEAD_SHADOW_SYNC:-1}"
export PTT_LEADS_READ_UPSTREAM="${PTT_LEADS_READ_UPSTREAM:-nest}"
export PTT_LEAD_REPLICA_SYNC="${PTT_LEAD_REPLICA_SYNC:-0}"
exec "$PYTHON" "$ROOT/scripts/staging_write_cutover_pilot.py" "$@"
