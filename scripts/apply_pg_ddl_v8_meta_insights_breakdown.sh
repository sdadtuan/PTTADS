#!/usr/bin/env bash
# Apply PostgreSQL DDL v8 — Meta Enterprise B8.1 (daily_performance_breakdown)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from ptt_crm.pg_schema import (
    apply_ddl_v8_meta_insights_breakdown,
    pg_daily_performance_breakdown_ready,
    pg_v3_ready,
)

if not pg_v3_ready():
    raise SystemExit("PG v3 OLTP not ready — apply base DDL first")

apply_ddl_v8_meta_insights_breakdown()
print("daily_performance_breakdown ready:", pg_daily_performance_breakdown_ready())
PY
