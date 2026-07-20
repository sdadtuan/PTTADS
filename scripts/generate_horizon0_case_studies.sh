#!/usr/bin/env bash
# Generate Horizon 0 pilot case study metrics + markdown
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

if [[ -f "$ROOT/deploy/env.horizon0-gate-a.example" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/deploy/env.horizon0-gate-a.example"
  set +a
fi

DAYS="${1:-28}"
"$PYTHON" -m ptt_crm.horizon0_pilot_case_study "$DAYS"
