#!/usr/bin/env bash
# Gate D — CWV + AEO schedule + crawl reminders (weekly)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
cd "$ROOT"
echo "==> SEO Gate D cron"
if [[ -n "${PTT_SEO_CRON_BASE_URL:-}" && -n "${PTT_SEO_CRON_SECRET:-}" ]]; then
  curl -fsS -X POST \
    -H "Authorization: Bearer ${PTT_SEO_CRON_SECRET}" \
    "${PTT_SEO_CRON_BASE_URL%/}/api/v1/seo/cron/gate-d"
  echo
else
  "$PYTHON" -c "
from ptt_seo.cron import run_gate_d_cron
import json
out = run_gate_d_cron()
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True):
    raise SystemExit(1)
"
fi
