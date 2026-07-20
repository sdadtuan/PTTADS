#!/usr/bin/env bash
# Staging Phase 3 gate pack — Portal + Temporal + Google + Hub PG
#
# Usage:
#   set -a && source deploy/env.staging-phase3.example && set +a
#   ./scripts/staging_phase3_gate_pack.sh
#
# Options (forwarded to Python):
#   --skip-temporal   skip Temporal docker/worker gate
#   --skip-playwright skip Playwright in QA aggregate
#   --skip-build      portal gate skips Next.js production build
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
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
exec "$PYTHON" "$ROOT/scripts/staging_phase3_gate_pack.py" "$@"
