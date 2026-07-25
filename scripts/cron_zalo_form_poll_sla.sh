#!/usr/bin/env bash
# Prod-S3 — enqueue zalo_form_poll_sla check (cron every 15 min alongside form poll)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
import os
from ptt_zalo.form_poll_sla import evaluate_form_poll_sla

os.environ.setdefault("PTT_ZALO_FORM_POLL_SLA", "1")
outcome = evaluate_form_poll_sla(dry_run=False)
print(outcome)
PY
