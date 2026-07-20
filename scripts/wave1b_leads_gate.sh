#!/usr/bin/env bash
# Wave 1b — CRM Leads legacy parity (activities, assign, audit on Nest + ops-web)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

export PTT_CRM_LEADS_LEGACY_UPSTREAM="${PTT_CRM_LEADS_LEGACY_UPSTREAM:-nest}"
export PTT_FLASK_CRM_LEADS_LEGACY_RETIRED="${PTT_FLASK_CRM_LEADS_LEGACY_RETIRED:-1}"
export PTT_LEADS_WRITE_UPSTREAM="${PTT_LEADS_WRITE_UPSTREAM:-nest}"
export WAVE1B_EXPECT_LEADS_LEGACY_NEST="${WAVE1B_EXPECT_LEADS_LEGACY_NEST:-1}"
export WAVE1B_SKIP_BUILD="${WAVE1B_SKIP_BUILD:-1}"

"$PYTHON" -m ptt_crm.wave1b_leads_gates
