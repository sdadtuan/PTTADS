#!/usr/bin/env bash
# Sprint 0 DDL — W5 prod id sequence + portal_client_users
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply Sprint 0 DDL (W5 prod id + portal users)"
echo "    DATABASE_URL=$DATABASE_URL"

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v3_sprint0, pg_sprint0_ready, pg_sprint0_migration_applied
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
apply_ddl_v3_sprint0()
assert pg_sprint0_ready(), 'crm_leads_prod_id_seq missing'
assert pg_sprint0_migration_applied(), 'schema_migrations sprint0 missing'
print('OK  Sprint 0 DDL applied')
"
