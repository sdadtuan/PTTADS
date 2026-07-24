#!/usr/bin/env bash
# Wave B13 — Meta Enterprise ops webhooks gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B12_SKIP_B11="${WAVE_B12_SKIP_B11:-1}"
export WAVE_B12_SKIP_PG="${WAVE_B12_SKIP_PG:-1}"
python3 -m ptt_crm.wave_b13_gates
