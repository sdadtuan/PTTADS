#!/usr/bin/env bash
# EM-11 — enqueue email_campaign_schedule_due every minute (systemd timer)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
cd "$ROOT"
"$PYTHON" - <<'PY'
from ptt_email.campaign_schedule import enqueue_due_scheduled_campaigns

out = enqueue_due_scheduled_campaigns()
print(out)
PY
