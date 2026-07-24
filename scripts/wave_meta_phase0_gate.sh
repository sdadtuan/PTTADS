#!/usr/bin/env bash
# Meta Enterprise Phase 0 — hub component extraction gate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

export WAVE_META_P0_SKIP_BUILD="${WAVE_META_P0_SKIP_BUILD:-0}"

echo "== Meta Phase 0 gate =="
"$PYTHON" -m ptt_crm.wave_meta_phase0_gates
