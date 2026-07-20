#!/usr/bin/env bash
# EM-9 / Wave 4 gate — prod pilot (Waves 1–3b + EM-5 Gate A)
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
export PTT_EMAIL_JOURNEYS_ENABLED="${PTT_EMAIL_JOURNEYS_ENABLED:-1}"
export PTT_EMAIL_PORTAL_ENABLED="${PTT_EMAIL_PORTAL_ENABLED:-1}"
export EM5_INCLUDE_WAVE_GATES=1
export EM5_EXPECT_EMAIL_ENABLED=1
export EM5_EXPECT_SEND_ENABLED=1
export EM5_EXPECT_JOURNEYS_ENABLED=1
export EM5_EXPECT_PORTAL_ENABLED=1
export EM5_SKIP_SOAK="${EM5_SKIP_SOAK:-1}"
export EM5_SKIP_BUILD="${EM5_SKIP_BUILD:-0}"
export WAVE4_SKIP_WAVE_REPORTS="${WAVE4_SKIP_WAVE_REPORTS:-0}"
export SKIP_CLICKHOUSE="${SKIP_CLICKHOUSE:-1}"
export WAVE4_SKIP_PHASE5="${WAVE4_SKIP_PHASE5:-0}"

mkdir -p "$PTT_ARTIFACTS_DIR"

REFRESH=""
for arg in "$@"; do
  case "$arg" in
    --refresh-wave) REFRESH="--refresh-wave" ;;
    --refresh-all) REFRESH="--refresh-all" ;;
  esac
done

if [[ "$REFRESH" == "--refresh-all" ]] || [[ "${WAVE4_REFRESH_ALL_GATES:-0}" == "1" ]]; then
  echo "==> Refresh EM-0..EM-4 foundation gates"
  bash "$ROOT/scripts/phase0_email_hub_kickoff_gate.sh"
  bash "$ROOT/scripts/phase1_email_ops_gate.sh"
  bash "$ROOT/scripts/phase2_email_send_mvp_gate.sh"
  bash "$ROOT/scripts/phase3_email_enterprise_gate.sh"
  bash "$ROOT/scripts/phase4_email_portal_gate.sh"
fi

if [[ "$REFRESH" == "--refresh-wave" ]] || [[ "$REFRESH" == "--refresh-all" ]] || [[ "${WAVE4_REFRESH_WAVE_GATES:-0}" == "1" ]]; then
  echo "==> Refresh Wave 1–3b gates"
  bash "$ROOT/scripts/phase6_email_send_platform_gate.sh"
  SKIP_CLICKHOUSE=1 bash "$ROOT/scripts/phase7_email_wave2_gate.sh"
  bash "$ROOT/scripts/phase8_email_wave3_gate.sh"
  bash "$ROOT/scripts/phase8b_email_wave3b_gate.sh"
fi

echo ""
echo "==> Wave 4 prod pilot gate pack"
"$PYTHON" -m ptt_crm.phase9_email_wave4_gates $REFRESH
RC=$?

echo ""
if [[ "$RC" -eq 0 ]]; then
  echo "OK  Wave 4 gate — $PTT_ARTIFACTS_DIR/phase9-email-wave4-report.json"
else
  echo "FAIL Wave 4 gate — see $PTT_ARTIFACTS_DIR/phase9-email-wave4-report.json" >&2
fi
exit "$RC"
