#!/usr/bin/env bash
# Apply PostgreSQL DDL v9 — Meta B12 creative registry
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
python3 - <<'PY'
from ptt_crm.pg_schema import apply_ddl_v9_meta_creative_registry

apply_ddl_v9_meta_creative_registry()
print("OK: DDL v9 meta creative registry applied")
PY
