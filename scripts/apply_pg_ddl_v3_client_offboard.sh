#!/usr/bin/env bash
# Apply Wave B7.1 client offboard DDL (audit + tenant_locked)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

DDL="$ROOT/docs/specs/2026-07-23-postgresql-ddl-v3-client-offboard.sql"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply PG client offboard migration (Wave B7.1-S1)"
echo "    DATABASE_URL=$DATABASE_URL"

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
print('OK  v3 prerequisite met')
"

if command -v psql >/dev/null 2>&1; then
  psql "$DATABASE_URL" -f "$DDL"
else
  echo "==> psql not found — applying via Python (psycopg2)"
  "$PYTHON" -c "from ptt_crm.pg_schema import apply_ddl_v3_client_offboard; apply_ddl_v3_client_offboard()"
fi

"$PYTHON" -c "
from ptt_crm.pg_schema import pg_client_offboard_ready, pg_client_offboard_migration_applied
assert pg_client_offboard_migration_applied(), 'schema_migrations client-offboard missing'
assert pg_client_offboard_ready(), 'client_offboard_audit or tenant_locked missing'
print('OK  client offboard migration applied')
"
