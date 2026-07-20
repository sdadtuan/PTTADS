#!/usr/bin/env bash
# EM-5 Gate A — prod pilot QA (runs EM-0..EM-4 reports check + soak + builds)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_EMAIL_ENABLED="${PTT_EMAIL_ENABLED:-1}"
export PTT_EMAIL_SEND_ENABLED="${PTT_EMAIL_SEND_ENABLED:-1}"
export PTT_EMAIL_JOURNEYS_ENABLED="${PTT_EMAIL_JOURNEYS_ENABLED:-0}"
export PTT_EMAIL_PORTAL_ENABLED="${PTT_EMAIL_PORTAL_ENABLED:-0}"
export EM5_EXPECT_EMAIL_ENABLED="${EM5_EXPECT_EMAIL_ENABLED:-1}"
export EM5_EXPECT_SEND_ENABLED="${EM5_EXPECT_SEND_ENABLED:-1}"
export EM5_EXPECT_JOURNEYS_ENABLED="${EM5_EXPECT_JOURNEYS_ENABLED:-0}"
export EM5_EXPECT_PORTAL_ENABLED="${EM5_EXPECT_PORTAL_ENABLED:-0}"
export EM5_SKIP_SOAK="${EM5_SKIP_SOAK:-1}"
export EM5_SKIP_NEST_SMOKE="${EM5_SKIP_NEST_SMOKE:-0}"
export EM5_SKIP_BUILD="${EM5_SKIP_BUILD:-0}"
export EM5_SKIP_PRIOR_REPORTS="${EM5_SKIP_PRIOR_REPORTS:-0}"
export EM5_INCLUDE_WAVE_GATES="${EM5_INCLUDE_WAVE_GATES:-1}"
export EM5_SKIP_WAVE_REPORTS="${EM5_SKIP_WAVE_REPORTS:-0}"
cd "$ROOT"

REFRESH=""
for arg in "$@"; do
  case "$arg" in
    --refresh-prior) REFRESH="--refresh-prior" ;;
  esac
done

if [[ "$REFRESH" == "--refresh-prior" ]] || [[ "${EM5_REFRESH_PRIOR_GATES:-0}" == "1" ]]; then
  echo "==> Refresh EM-0..EM-4 gate reports"
  bash "$ROOT/scripts/phase0_email_hub_kickoff_gate.sh"
  bash "$ROOT/scripts/phase1_email_ops_gate.sh"
  bash "$ROOT/scripts/phase2_email_send_mvp_gate.sh"
  bash "$ROOT/scripts/phase3_email_enterprise_gate.sh"
  bash "$ROOT/scripts/phase4_email_portal_gate.sh"
  if [[ "${EM5_INCLUDE_WAVE_GATES:-1}" == "1" ]]; then
    echo ""
    echo "==> Refresh Wave 1–3b gate reports (EM-6..EM-8b)"
    bash "$ROOT/scripts/phase6_email_send_platform_gate.sh"
    SKIP_CLICKHOUSE=1 bash "$ROOT/scripts/phase7_email_wave2_gate.sh"
    bash "$ROOT/scripts/phase8_email_wave3_gate.sh"
    bash "$ROOT/scripts/phase8b_email_wave3b_gate.sh"
  fi
fi

echo ""
echo "==> EM-5 prod pilot gate pack"
"$PYTHON" -m ptt_crm.phase5_email_gates $REFRESH
RC=$?

echo ""
if [[ "$RC" -eq 0 ]]; then
  echo "OK  EM-5 gate — $PTT_ARTIFACTS_DIR/phase5-email-pilot-gate-report.json"
else
  echo "FAIL EM-5 gate — see $PTT_ARTIFACTS_DIR/phase5-email-pilot-gate-report.json" >&2
fi
exit "$RC"
