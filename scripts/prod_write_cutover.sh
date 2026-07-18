#!/usr/bin/env bash
# Prod write cutover assistant — runbook docs/runbooks/cutover-leads-write-phase2.md §4–§8
#
# Default: dry-run preflight + rollback evidence
#   ./scripts/prod_write_cutover.sh
#
# Apply sync_mode only (after VPS env files updated manually):
#   ./scripts/prod_write_cutover.sh --apply
#
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
exec "$PYTHON" "$ROOT/scripts/prod_write_cutover.py" "$@"
