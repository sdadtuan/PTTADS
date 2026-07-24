#!/usr/bin/env bash
# Apply PostgreSQL DDL v7 — Meta Enterprise B11 (meta_pixels, intelligence snapshots)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from ptt_crm.pg_schema import (
    apply_ddl_v7_meta_advanced,
    pg_meta_intelligence_snapshots_ready,
    pg_meta_pixels_ready,
    pg_v3_ready,
)

if not pg_v3_ready():
    raise SystemExit("PG v3 OLTP not ready — apply base DDL first")

apply_ddl_v7_meta_advanced()
print("meta_pixels ready:", pg_meta_pixels_ready())
print("meta_intelligence_snapshots ready:", pg_meta_intelligence_snapshots_ready())
PY
