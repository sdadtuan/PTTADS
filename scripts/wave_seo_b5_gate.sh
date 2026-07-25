#!/usr/bin/env bash
# Wave SEO B5 — client portal prod gate (module files + QA + portal-seo jest).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export WAVE_SEO_B5_SKIP_JEST="${WAVE_SEO_B5_SKIP_JEST:-0}"
python3 -m ptt_crm.wave_seo_b5_gates
