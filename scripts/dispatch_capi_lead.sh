#!/usr/bin/env bash
# Meta CAPI Lead dispatch — manual replay / pilot (Phase 2 M5)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_CAPI_ENABLED="${PTT_CAPI_ENABLED:-1}"
LEAD_ID="${1:-}"
CLIENT_ID="${2:-${PTT_CAPI_PILOT_CLIENTS:-}}"
if [[ -z "$LEAD_ID" || -z "$CLIENT_ID" ]]; then
  echo "Usage: LEAD_ID CLIENT_ID [stub=1]" >&2
  echo "  or:  $0 <lead_id> <client_uuid>" >&2
  exit 1
fi
STUB="${PTT_CAPI_STUB:-0}"
cd "$ROOT"
echo "==> CAPI dispatch lead=$LEAD_ID client=$CLIENT_ID stub=$STUB"
"$PYTHON" -c "
from ptt_meta.capi_dispatch import dispatch_lead_capi, capi_stats
import json
import os
if os.environ.get('PTT_CAPI_STUB', '0') in ('1', 'true', 'yes'):
    os.environ['PTT_CAPI_STUB'] = '1'
out = dispatch_lead_capi(lead_id=int('${LEAD_ID}'), client_id='${CLIENT_ID}')
stats = capi_stats(hours=24)
print(json.dumps({'dispatch': out, 'stats_24h': stats}, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
