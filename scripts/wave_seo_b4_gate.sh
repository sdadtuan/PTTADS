#!/usr/bin/env bash
# Wave SEO B4 full gate — module files + Python QA tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m ptt_crm.wave_seo_b4_gates
