#!/usr/bin/env bash
# Apply PostgreSQL DDL v2 — crm_leads read replica (Phase 1b Bước 5)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DDL="$ROOT/docs/specs/2026-07-17-postgresql-ddl-v2-leads.sql"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply PG DDL v2 (crm_leads read replica)"
echo "    DATABASE_URL=$DATABASE_URL"

if command -v psql >/dev/null 2>&1; then
  psql "$DATABASE_URL" -f "$DDL"
else
  echo "==> psql not found — applying via Python"
  cd "$ROOT"
  "$PYTHON" -c "from ptt_crm.pg_schema import apply_ddl_v2; apply_ddl_v2()"
fi

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_leads_migration_applied, pg_leads_replica_ready, pg_leads_stats
assert pg_leads_replica_ready(), 'crm_leads table missing'
assert pg_leads_migration_applied(), 'schema_migrations v2 missing'
print('OK  crm_leads replica ready', pg_leads_stats())
"
