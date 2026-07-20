#!/usr/bin/env bash
# Horizon 0 — Gate A pack (SEO + Email prod pilot + delivery admin retire + case studies)
#
# Usage:
#   ./scripts/horizon0_gate_a_pack.sh preflight     # gates only, soak skipped
#   ./scripts/horizon0_gate_a_pack.sh soak          # record today's soak snapshot
#   ./scripts/horizon0_gate_a_pack.sh evaluate      # evaluate soak + merge signoffs
#   ./scripts/horizon0_gate_a_pack.sh full          # preflight + bootstrap soak + evaluate
#   ./scripts/horizon0_gate_a_pack.sh case-studies  # pull pilot metrics from PG
#   ./scripts/horizon0_gate_a_pack.sh delivery-admin # partial Flask SEO/email admin retire (dry-run)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

ENV_EXAMPLE="$ROOT/deploy/env.horizon0-gate-a.example"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

MODE="${1:-preflight}"

case "$MODE" in
  preflight)
    export EM5_SKIP_SOAK=1
    export PHASE5_SKIP_SOAK=1
    echo "==> Horizon 0 preflight (gates, soak skipped)"
    bash "$ROOT/scripts/phase5_prod_cutover_gate.sh"
    bash "$ROOT/scripts/phase5_email_prod_pilot_gate.sh"
    export EM5_SKIP_NEST_SMOKE="${EM5_SKIP_NEST_SMOKE:-1}"
    bash "$ROOT/scripts/phase12_email_automation_gate.sh" || true
    "$PYTHON" -m ptt_crm.phase5_delivery_admin_retirement_gates
    "$PYTHON" -m ptt_crm.horizon0_gate_a_signoff preflight
    ;;
  soak)
    export EM5_SKIP_SOAK=0
    export PHASE5_SKIP_SOAK=0
    echo "==> Record soak snapshots"
    "$ROOT/scripts/phase5_soak_record.sh"
    "$ROOT/scripts/phase5_email_soak_record.sh"
    "$PYTHON" -m ptt_crm.horizon0_gate_a_signoff evaluate
    ;;
  evaluate)
    export EM5_SKIP_SOAK=0
    export PHASE5_SKIP_SOAK=0
    "$PYTHON" -m ptt_crm.horizon0_gate_a_signoff evaluate
    ;;
  full)
    export HORIZON0_BOOTSTRAP_SOAK=1
    export EM5_SKIP_SOAK=1
    export PHASE5_SKIP_SOAK=1
    echo "==> Horizon 0 full (staging bootstrap soak)"
    bash "$ROOT/scripts/phase5_prod_cutover_gate.sh"
    bash "$ROOT/scripts/phase5_email_prod_pilot_gate.sh"
    export EM5_SKIP_NEST_SMOKE="${EM5_SKIP_NEST_SMOKE:-1}"
    "$PYTHON" -m ptt_crm.phase5_delivery_admin_retirement_gates
    export EM5_SKIP_SOAK=0
    export PHASE5_SKIP_SOAK=0
    "$PYTHON" -m ptt_crm.horizon0_gate_a_signoff full
    ;;
  case-studies)
    "$PYTHON" -m ptt_crm.horizon0_pilot_case_study "${2:-28}"
    ;;
  delivery-admin)
    chmod +x "$ROOT/scripts/close_flask_retirement_delivery_admin.sh"
    sudo -E "$ROOT/scripts/close_flask_retirement_delivery_admin.sh"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

RC=$?
echo ""
if [[ -f "$PTT_ARTIFACTS_DIR/horizon0-gate-a-signoff.json" ]]; then
  echo "Sign-off artifact: $PTT_ARTIFACTS_DIR/horizon0-gate-a-signoff.json"
fi
exit "$RC"
