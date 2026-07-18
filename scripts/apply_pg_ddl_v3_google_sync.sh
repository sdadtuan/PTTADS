#!/usr/bin/env bash
# Phase 3 G2 — google_insights_sync_state DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply Google sync DDL"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v3_google_sync, pg_google_sync_ready
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
apply_ddl_v3_google_sync()
assert pg_google_sync_ready(), 'google_insights_sync_state missing'
print('OK  Google sync DDL applied')
"
