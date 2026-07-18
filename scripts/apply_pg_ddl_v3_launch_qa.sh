#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
[[ -x "$ROOT/.venv/bin/python" ]] && PYTHON="$ROOT/.venv/bin/python"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_v3_launch_qa, pg_launch_qa_ready
assert pg_v3_ready(), 'Apply v3 first'
apply_ddl_v3_launch_qa()
assert pg_launch_qa_ready()
print('OK  Launch QA DDL applied')
"
