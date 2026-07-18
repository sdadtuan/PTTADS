#!/usr/bin/env bash
# Verify Sentry Phase 2 observability hooks (X-UAT-02)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_SENTRY_CLOSURE_WAIVER="${PTT_SENTRY_CLOSURE_WAIVER:-1}"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.phase2_prod_closure import verify_sentry_phase2
import json, sys
out = verify_sentry_phase2()
print(json.dumps(out, indent=2, default=str))
sys.exit(0 if out.get('ok') else 1)
"
