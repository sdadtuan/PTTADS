#!/usr/bin/env bash
# Wave 2 — CRM Customers + Intake cutover (ops-web + Nest)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

export PTT_CRM_CUSTOMERS_UPSTREAM="${PTT_CRM_CUSTOMERS_UPSTREAM:-ops-web}"
export PTT_FLASK_CRM_CUSTOMERS_RETIRED="${PTT_FLASK_CRM_CUSTOMERS_RETIRED:-1}"
export PTT_CRM_INTAKE_UPSTREAM="${PTT_CRM_INTAKE_UPSTREAM:-ops-web}"
export PTT_FLASK_CRM_INTAKE_RETIRED="${PTT_FLASK_CRM_INTAKE_RETIRED:-1}"
export WAVE2_EXPECT_CUSTOMERS_OPS_WEB="${WAVE2_EXPECT_CUSTOMERS_OPS_WEB:-1}"
export WAVE2_EXPECT_INTAKE_OPS_WEB="${WAVE2_EXPECT_INTAKE_OPS_WEB:-1}"

"$PYTHON" -m ptt_crm.wave2_gates
