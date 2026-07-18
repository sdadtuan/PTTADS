#!/usr/bin/env bash
# Phase 3 P4 — creative_submissions DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply P4 creatives DDL (creative_submissions)"
echo "    DATABASE_URL=$DATABASE_URL"

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v3_creatives, pg_creatives_ready, pg_creatives_migration_applied
assert pg_v3_ready(), 'Apply v3 first: ./scripts/apply_pg_ddl_v3.sh'
apply_ddl_v3_creatives()
assert pg_creatives_ready(), 'creative_submissions missing'
assert pg_creatives_migration_applied(), 'schema_migrations creatives missing'
print('OK  P4 creatives DDL applied')
"
