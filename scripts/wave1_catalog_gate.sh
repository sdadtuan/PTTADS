#!/usr/bin/env bash
# Wave 1 — CRM Catalog cutover (ops-web + Nest, Flask catalog readonly)
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

"$PYTHON" -m ptt_crm.wave1_catalog_gates
