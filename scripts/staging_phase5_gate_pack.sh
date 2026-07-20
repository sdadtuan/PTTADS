#!/usr/bin/env bash
# Phase 5 — Flask monolith retirement gate pack (staging / pre-prod)
#
# Usage:
#   set -a && source deploy/env.phase5-flask-retire.example && set +a
#   ./scripts/staging_phase5_gate_pack.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
ENV_FILE="${PTT_PHASE5_ENV:-$ROOT/deploy/env.phase5-flask-retire.example}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
exec "$PYTHON" "$ROOT/scripts/staging_phase5_gate_pack.py" "$@"
