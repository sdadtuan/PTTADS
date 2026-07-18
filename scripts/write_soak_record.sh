#!/usr/bin/env bash
# Record write dual-run sample for 48h soak evidence (hourly timer)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
SAMPLE="${SAMPLE:-50}"
cd "$ROOT"
echo "==> Write soak record (sample=$SAMPLE)"
"$ROOT/scripts/dual_run_write_check.py" --sample "$SAMPLE" --record --quiet
