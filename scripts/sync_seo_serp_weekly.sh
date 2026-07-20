#!/usr/bin/env bash
# SEO SERP capture — weekly (Gate B) or standalone timer
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_SERP_SCHEDULE_ENABLED="${PTT_SERP_SCHEDULE_ENABLED:-1}"
cd "$ROOT"
echo "==> SEO SERP scheduled capture"
if [[ -n "${PTT_SEO_CRON_BASE_URL:-}" && -n "${PTT_SEO_CRON_SECRET:-}" ]]; then
  curl -fsS -X POST \
    -H "Authorization: Bearer ${PTT_SEO_CRON_SECRET}" \
    "${PTT_SEO_CRON_BASE_URL%/}/api/v1/seo/cron/serp"
  echo
else
  "$PYTHON" -c "
from ptt_seo.cron import run_serp_cron
import json
out = run_serp_cron()
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
fi
