#!/usr/bin/env bash
# Apply staff auth DDL (Phase 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
DDL="$ROOT/docs/specs/2026-07-20-postgresql-ddl-staff-auth.sql"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply staff auth DDL"
echo "    DATABASE_URL=$DATABASE_URL"

if command -v psql >/dev/null 2>&1; then
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$DDL"
else
  echo "==> psql not found — applying via Python (psycopg2)"
  "$PYTHON" -c "
from pathlib import Path
from ptt_crm.pg_schema import _apply_sql_file
_apply_sql_file(Path('$DDL'))
"
fi

echo "OK  staff auth DDL applied"
