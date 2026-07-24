#!/usr/bin/env bash
# Wave B11 — Meta Enterprise Advanced gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B10_SKIP_PG="${WAVE_B10_SKIP_PG:-1}"
python3 -m ptt_crm.wave_b11_gates
