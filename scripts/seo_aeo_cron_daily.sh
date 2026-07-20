#!/usr/bin/env bash
# SEO/AEO daily cron — GSC sync, GA4 sync, due report schedules (P3c)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
cd "$ROOT"
export PTT_GSC_SYNC_ENABLED="${PTT_GSC_SYNC_ENABLED:-1}"
export PTT_GA4_SYNC_ENABLED="${PTT_GA4_SYNC_ENABLED:-1}"
DAYS="${1:-28}"
echo "==> SEO/AEO daily cron (days=$DAYS)"
if [[ -n "${PTT_SEO_CRON_BASE_URL:-}" && -n "${PTT_SEO_CRON_SECRET:-}" ]]; then
  curl -fsS -X POST \
    -H "Authorization: Bearer ${PTT_SEO_CRON_SECRET}" \
    "${PTT_SEO_CRON_BASE_URL%/}/api/v1/seo/cron/daily?days=${DAYS}"
  echo
else
  "$PYTHON" -c "
from ptt_seo.cron import run_daily_cron
import json
out = run_daily_cron(days=int('${DAYS}'))
print(json.dumps(out, indent=2, default=str))
if not out.get('ok'):
    raise SystemExit(1)
"
fi
