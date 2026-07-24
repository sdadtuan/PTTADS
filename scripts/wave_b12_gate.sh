#!/usr/bin/env bash
# Wave B12 — Meta Enterprise creative registry gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B11_SKIP_PG="${WAVE_B11_SKIP_PG:-1}"
export WAVE_B11_SKIP_B10="${WAVE_B11_SKIP_B10:-1}"
python3 -m ptt_crm.wave_b12_gates
