#!/usr/bin/env bash
# Apply PG DDL for lead ingest rules snapshot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import apply_ddl_v3_leads_ingest_config, pg_ingest_rules_migration_applied
apply_ddl_v3_leads_ingest_config()
print('OK  ingest rules DDL applied:', pg_ingest_rules_migration_applied())
"
