#!/usr/bin/env bash
# Prod cutover gates — OpenAPI freeze + 48h soak + live dual-run
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
export PTT_WRITE_SOAK_LOG="${PTT_WRITE_SOAK_LOG:-$ROOT/.local-dev/write-soak-evidence.jsonl}"
exec "$PYTHON" "$ROOT/scripts/write_cutover_prod_gates.py" "$@"
