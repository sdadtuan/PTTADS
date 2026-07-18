#!/usr/bin/env bash
# PG crm_leads → SQLite shadow sync (Phase 2 W2)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_LEAD_SHADOW_SYNC="${PTT_LEAD_SHADOW_SYNC:-1}"
MODE="${1:-incremental}"
cd "$ROOT"
echo "==> Lead shadow sync (mode=$MODE)"
"$PYTHON" -c "
from ptt_crm.lead_shadow_sync import (
    sync_shadow_full,
    sync_shadow_incremental,
    reconcile_leads_pg_primary,
)
import json
mode = '$MODE'
if mode == 'full':
    out = sync_shadow_full()
elif mode == 'reconcile':
    out = reconcile_leads_pg_primary(sample_size=int('${SAMPLE:-50}'))
else:
    out = sync_shadow_incremental()
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True):
    raise SystemExit(1)
"
