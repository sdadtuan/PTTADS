#!/usr/bin/env bash
# Wave Z2 — enqueue zalo_form_lead_poll for all active forms (cron every 5–15 min)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
import os
from ptt_zalo.form_lead_poll import poll_zalo_form_leads

os.environ.setdefault("PTT_ZALO_FORM_POLL", "1")
outcome = poll_zalo_form_leads()
print(outcome)
if not outcome.get("ok") and not outcome.get("skipped"):
    raise SystemExit(1)
PY
