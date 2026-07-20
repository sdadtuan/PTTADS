#!/usr/bin/env bash
# EM-12 gate — enterprise automation (journeys execution + A/B experiments)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_EMAIL_ENABLED="${PTT_EMAIL_ENABLED:-1}"
export PTT_EMAIL_SEND_ENABLED="${PTT_EMAIL_SEND_ENABLED:-1}"
export PTT_EMAIL_JOURNEYS_ENABLED="${PTT_EMAIL_JOURNEYS_ENABLED:-1}"

fail=0

check_file() {
  local path="$1"
  if [[ -f "$ROOT/$path" ]]; then
    echo "OK  $path"
  else
    echo "FAIL missing $path" >&2
    fail=1
  fi
}

echo "==> EM-12 artifact checks"
check_file "deploy/sql/email_mkt_em12_automation.sql"
check_file "scripts/apply_pg_ddl_email_mkt_em12.sh"
check_file "ptt_email/experiments.py"
check_file "ptt_email/triggers.py"
check_file "ptt_jobs/handlers/email_experiment_rollup.py"
check_file "ptt_jobs/handlers/email_journey_trigger_events.py"
check_file "ptt_temporal/workflows/email_journey.py"
check_file "services/ptt-crm-api/src/email-marketing/email-marketing-experiment.repository.ts"
check_file "services/ops-web/src/components/email/JourneyCanvasEditor.tsx"
check_file "services/ops-web/src/components/email/CampaignExperimentPanel.tsx"

echo ""
echo "==> EM-12 pytest"
"$PYTHON" -m pytest tests/test_email_mkt_em12_automation.py tests/test_email_mkt_em11_prod_ops.py -q
RC=$?
if [[ "$RC" -ne 0 ]]; then
  fail=1
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "OK  EM-12 enterprise automation gate"
  exit 0
fi
echo "FAIL EM-12 enterprise automation gate" >&2
exit 1
