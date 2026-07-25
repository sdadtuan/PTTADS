#!/usr/bin/env bash
# SEO/AEO UI spec §12 handoff gate — Python QA + optional Playwright (ops-web, no Flask)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SEO_HANDOFF_SKIP_E2E="${SEO_HANDOFF_SKIP_E2E:-1}"
python3 -m ptt_crm.seo_handoff_gates
