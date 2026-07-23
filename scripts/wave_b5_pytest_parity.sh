#!/usr/bin/env bash
# Wave B5 pytest parity — lifecycle + tasks + TMMT + finance
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m pytest \
  tests/test_crm_lead_presales.py \
  tests/test_crm_lead_presales_contract.py \
  tests/test_crm_service_lifecycle.py \
  tests/test_crm_svc_tasks.py \
  tests/test_crm_lead_presales_marketing_plan.py \
  tests/test_crm_svc_finance_presales_on_lead.py \
  -q "$@"
