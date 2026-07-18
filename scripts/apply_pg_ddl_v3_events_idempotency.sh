#!/usr/bin/env bash
# Apply domain_events idempotency_key migration (Phase 2 P1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

DDL="$ROOT/docs/specs/2026-07-17-postgresql-ddl-v3-domain-events-idempotency.sql"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply PG domain_events idempotency migration"
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
  "$PYTHON" -c "from ptt_crm.pg_schema import apply_ddl_v3_events_idempotency; apply_ddl_v3_events_idempotency()"
fi

"$PYTHON" -c "
from ptt_crm.pg_schema import pg_domain_events_idempotency_ready, pg_events_idempotency_migration_applied
assert pg_events_idempotency_migration_applied(), 'schema_migrations idempotency missing'
assert pg_domain_events_idempotency_ready(), 'idempotency_key column missing'
print('OK  domain_events idempotency migration applied')
"
