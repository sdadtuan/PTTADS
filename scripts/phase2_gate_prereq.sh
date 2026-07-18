#!/usr/bin/env bash
# Phase 2 gate prerequisites — idempotency DDL + shadow repair (run before dual-run gates)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_LEAD_SHADOW_SYNC="${PTT_LEAD_SHADOW_SYNC:-1}"

cd "$ROOT"
echo "==> Phase 2 gate prerequisites"
"$PYTHON" -c "
from ptt_crm.phase2_prereqs import ensure_phase2_write_gates
import json
out = ensure_phase2_write_gates(repair_shadow=True)
print(json.dumps(out, indent=2, default=str))
if not out.get('ok'):
    raise SystemExit(1)
print('OK  phase2 prerequisites')
"
