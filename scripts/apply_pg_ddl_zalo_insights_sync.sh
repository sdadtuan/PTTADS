#!/usr/bin/env bash
# Wave Z1 — zalo_insights_sync_state DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply Zalo insights sync DDL"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_zalo_insights_sync, pg_zalo_sync_ready
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
apply_ddl_zalo_insights_sync()
assert pg_zalo_sync_ready(), 'zalo_insights_sync_state missing'
print('OK  Zalo insights sync DDL applied')
"
