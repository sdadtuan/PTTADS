#!/usr/bin/env bash
# Wave SEO B6 — BI + Gate D/E enterprise gate (module files + QA + infra artifacts).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m ptt_crm.wave_seo_b6_gates
