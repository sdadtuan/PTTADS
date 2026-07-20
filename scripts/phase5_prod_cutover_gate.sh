#!/usr/bin/env bash
# Phase 5 gate pack — governance, experiments, portal bridge (+ optional soak)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export SEO_AEO_DB="${SEO_AEO_DB:-pg}"
export PTT_SEO_GOVERNANCE_ENABLED="${PTT_SEO_GOVERNANCE_ENABLED:-1}"
export PTT_SEO_EXPERIMENTS_ENABLED="${PTT_SEO_EXPERIMENTS_ENABLED:-0}"
export PTT_PORTAL_SEO_ENABLED="${PTT_PORTAL_SEO_ENABLED:-0}"
export PHASE5_EXPECT_GOVERNANCE="${PHASE5_EXPECT_GOVERNANCE:-1}"
export PHASE5_EXPECT_PORTAL="${PHASE5_EXPECT_PORTAL:-0}"
export PHASE5_EXPECT_EXPERIMENTS="${PHASE5_EXPECT_EXPERIMENTS:-0}"
export PHASE5_SKIP_SOAK="${PHASE5_SKIP_SOAK:-1}"
export PHASE5_SKIP_PORTAL_SIGNOFF="${PHASE5_SKIP_PORTAL_SIGNOFF:-1}"
cd "$ROOT"

echo "==> Phase 5 prod cutover gate"
"$PYTHON" -m ptt_crm.phase5_prod_gates
echo "OK  Phase 5 gate — see .local-dev/phase5-gate-report.json"
