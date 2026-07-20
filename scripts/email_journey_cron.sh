#!/usr/bin/env bash
# EM-11 — enqueue journey enroll scan + tick (systemd timer, every minute)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
export PTT_EMAIL_JOURNEYS_ENABLED="${PTT_EMAIL_JOURNEYS_ENABLED:-1}"
cd "$ROOT"
"$PYTHON" - <<'PY'
from ptt_email.journey_engine import enqueue_journey_cron_jobs

print(enqueue_journey_cron_jobs())
PY
