#!/usr/bin/env bash
# Wave B4 — run Python funnel pytest parity subset.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" -m pytest \
  tests/test_lead_review_queue.py \
  tests/test_lead_care_pipeline.py \
  tests/test_crm_lead_presales.py \
  tests/test_crm_lead_presales_marketing_plan.py \
  -q "$@"
