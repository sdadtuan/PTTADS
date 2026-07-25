#!/usr/bin/env bash
# Wave SEO B7 — Gate A go-live gate (module files + QA + nginx + prior waves).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export WAVE_SEO_B7_SKIP_PRIOR="${WAVE_SEO_B7_SKIP_PRIOR:-0}"
export WAVE_SEO_B5_SKIP_JEST="${WAVE_SEO_B5_SKIP_JEST:-1}"
python3 -m ptt_crm.wave_seo_b7_gates
