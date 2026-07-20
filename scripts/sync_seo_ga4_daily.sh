#!/usr/bin/env bash
# SEO GA4 OAuth daily sync — all connected clients (Phase 4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_GA4_SYNC_ENABLED="${PTT_GA4_SYNC_ENABLED:-1}"
DAYS="${1:-28}"
STUB="${PTT_GA4_SYNC_STUB:-0}"
cd "$ROOT"
echo "==> SEO GA4 daily sync (days=$DAYS stub=$STUB)"
"$PYTHON" -c "
from ptt_seo.connectors.ga4_sync import sync_all_ga4_customers
import json
out = sync_all_ga4_customers(days=int('${DAYS}'))
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
