#!/usr/bin/env bash
# Wave 1 full — catalog + leads legacy + Flask UI redirect + soak
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

export PTT_CRM_CATALOG_UPSTREAM="${PTT_CRM_CATALOG_UPSTREAM:-ops-web}"
export PTT_FLASK_CRM_CATALOG_RETIRED="${PTT_FLASK_CRM_CATALOG_RETIRED:-1}"
export WAVE1_EXPECT_CATALOG_OPS_WEB="${WAVE1_EXPECT_CATALOG_OPS_WEB:-1}"
export WAVE1_SKIP_JEST="${WAVE1_SKIP_JEST:-1}"

export PTT_CRM_LEADS_LEGACY_UPSTREAM="${PTT_CRM_LEADS_LEGACY_UPSTREAM:-nest}"
export PTT_FLASK_CRM_LEADS_LEGACY_RETIRED="${PTT_FLASK_CRM_LEADS_LEGACY_RETIRED:-1}"
export PTT_LEADS_WRITE_UPSTREAM="${PTT_LEADS_WRITE_UPSTREAM:-nest}"
export WAVE1B_EXPECT_LEADS_LEGACY_NEST="${WAVE1B_EXPECT_LEADS_LEGACY_NEST:-1}"
export WAVE1B_SKIP_BUILD="${WAVE1B_SKIP_BUILD:-1}"

export PTT_CRM_LEADS_UPSTREAM="${PTT_CRM_LEADS_UPSTREAM:-ops-web}"
export PTT_FLASK_CRM_LEADS_UI_RETIRED="${PTT_FLASK_CRM_LEADS_UI_RETIRED:-1}"
export WAVE1F_EXPECT_LEADS_OPS_WEB="${WAVE1F_EXPECT_LEADS_OPS_WEB:-1}"
export WAVE1F_SKIP_SOAK="${WAVE1F_SKIP_SOAK:-1}"

"$PYTHON" -m ptt_crm.wave1_full_gates

if [[ "${WAVE1_INCLUDE_B4:-1}" == "1" ]]; then
  echo ""
  echo "== Wave B4 funnel gates =="
  export WAVE_B4_SKIP_JEST="${WAVE_B4_SKIP_JEST:-1}"
  bash "$ROOT/scripts/wave_b4_gate.sh"
fi
