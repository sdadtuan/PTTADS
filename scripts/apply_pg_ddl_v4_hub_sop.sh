#!/usr/bin/env bash
# Phase 3 D — hub_campaigns + SOP PG DDL v4
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply DDL v4 Hub/SOP"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v4_hub_sop, pg_hub_sop_ready
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
apply_ddl_v4_hub_sop()
assert pg_hub_sop_ready(), 'hub_campaigns/sop tables missing'
print('OK  DDL v4 Hub/SOP applied')
"
