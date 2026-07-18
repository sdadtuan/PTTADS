#!/usr/bin/env bash
# P0-10 — KPI dictionary seed (spec §8)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import apply_kpi_dictionary_seed, pg_kpi_definitions_ready
apply_kpi_dictionary_seed()
assert pg_kpi_definitions_ready(), 'kpi_definitions seed failed'
print('OK  KPI dictionary seeded')
"
