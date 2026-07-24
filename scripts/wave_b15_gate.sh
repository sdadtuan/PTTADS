#!/usr/bin/env bash
# Wave B15 — Meta Enterprise Ads Ops UI gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B15_SKIP_B14="${WAVE_B15_SKIP_B14:-1}"
python3 -m ptt_crm.wave_b15_gates
