#!/usr/bin/env bash
# SEO/AEO weekly cron — freshness scan + SERP capture (P3c / Gate B)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
cd "$ROOT"
export PTT_FRESHNESS_SCAN_ENABLED="${PTT_FRESHNESS_SCAN_ENABLED:-1}"
echo "==> SEO/AEO weekly cron (freshness)"
if [[ -n "${PTT_SEO_CRON_BASE_URL:-}" && -n "${PTT_SEO_CRON_SECRET:-}" ]]; then
  curl -fsS -X POST \
    -H "Authorization: Bearer ${PTT_SEO_CRON_SECRET}" \
    "${PTT_SEO_CRON_BASE_URL%/}/api/v1/seo/cron/weekly"
  echo
else
  "$PYTHON" -c "
from ptt_seo.cron import run_weekly_cron
import json
out = run_weekly_cron()
print(json.dumps(out, indent=2, default=str))
if not out.get('ok'):
    raise SystemExit(1)
"
fi
