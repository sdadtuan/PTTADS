#!/usr/bin/env bash
# Wave B14 — Meta Enterprise warehouse BI gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B14_SKIP_B13="${WAVE_B14_SKIP_B13:-1}"
python3 -m ptt_crm.wave_b14_gates
