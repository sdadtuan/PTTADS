#!/usr/bin/env bash
# Wave Z3 — creative channel DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
python3 - <<'PY'
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_zalo_z3, pg_zalo_z3_ready
assert pg_v3_ready(), 'pg v3 not ready — apply v3 DDL first'
apply_ddl_zalo_z3()
assert pg_zalo_z3_ready(), 'creative_submissions.channel missing'
print('OK: Zalo Z3 DDL applied')
PY
