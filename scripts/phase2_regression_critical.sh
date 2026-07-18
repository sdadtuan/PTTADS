#!/usr/bin/env bash
# Regression L01–L26 critical subset (X-UAT-01)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
echo "==> Phase 2 regression critical (L01–L26 subset)"
"$PYTHON" -c "
from ptt_crm.phase2_prod_closure import verify_regression_critical
import json, sys
out = verify_regression_critical()
print(json.dumps({'ok': out.get('ok'), 'tests_run': out.get('tests_run'), 'modules': len(out.get('modules', []))}, indent=2))
if not out.get('ok'):
    print(out.get('output_tail', '')[-2000:], file=sys.stderr)
sys.exit(0 if out.get('ok') else 1)
"
