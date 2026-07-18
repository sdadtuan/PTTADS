#!/usr/bin/env bash
# Process LeadCreated outbox → CAPI enqueue (Sprint 0 prod pilot)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
BATCH="${CAPI_BATCH:-50}"
SINCE_HOURS="${CAPI_SINCE_HOURS:-72}"
cd "$ROOT"
echo "==> LeadCreated → CAPI enqueue (batch=$BATCH since=${SINCE_HOURS}h)"
"$PYTHON" -c "
from ptt_meta.lead_created_subscriber import process_lead_created_outbox
import json, os
out = process_lead_created_outbox(
    batch_size=int(os.environ.get('CAPI_BATCH', '50')),
    since_hours=int(os.environ.get('CAPI_SINCE_HOURS', '72')),
)
print(json.dumps(out, indent=2))
raise SystemExit(0 if out.get('ok', True) else 1)
"
