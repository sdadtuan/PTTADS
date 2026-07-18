#!/usr/bin/env bash
# CI — OpenAPI write contract freeze gate (Phase 2 W3)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"

echo "==> OpenAPI write freeze check"
"$PYTHON" -c "from tests.leads_v1_write_contract import assert_write_openapi_frozen; assert_write_openapi_frozen(); print('OK  leads-v1-write.openapi.yaml frozen v1.0.0')"

echo "==> Write contract unit tests"
"$PYTHON" -m unittest tests.test_leads_v1_write_contract -q

echo "OK  write OpenAPI freeze CI passed"
