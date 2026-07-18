#!/usr/bin/env bash
# Phase 4 F1 — campaign_write_requests DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v5_campaign_writes, pg_campaign_writes_ready
assert pg_v3_ready(), 'Apply v3 first'
apply_ddl_v5_campaign_writes()
assert pg_campaign_writes_ready()
print('OK  DDL v5 campaign writes applied')
"
