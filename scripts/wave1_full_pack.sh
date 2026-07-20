#!/usr/bin/env bash
# Wave 1 full — orchestrator (preflight | bootstrap-soak | full | signoff)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

ENV_EXAMPLE="$ROOT/deploy/env.crm-flask-migration.example"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

MODE="${1:-preflight}"

case "$MODE" in
  preflight)
    chmod +x "$ROOT/scripts/wave1_full_gate.sh"
    "$ROOT/scripts/wave1_full_gate.sh"
    ;;
  bootstrap-soak)
    export WAVE1_BOOTSTRAP_SOAK=1
    "$PYTHON" -m ptt_crm.wave1_full_signoff bootstrap-soak
    ;;
  full)
    echo "==> Wave 1 full (staging bootstrap soak — NOT for prod)"
    export WAVE1_BOOTSTRAP_SOAK=1
    export WAVE1F_SKIP_SOAK=0
    export WAVE1_MARK_MANUAL_UAT=1
    "$PYTHON" -m ptt_crm.wave1_full_signoff bootstrap-soak
    chmod +x "$ROOT/scripts/wave1_full_gate.sh"
    "$ROOT/scripts/wave1_full_gate.sh"
    "$PYTHON" -m ptt_crm.wave1_full_signoff merge
    ;;
  signoff)
    export WAVE1F_SKIP_SOAK="${WAVE1F_SKIP_SOAK:-0}"
    "$PYTHON" -m ptt_crm.wave1_full_signoff merge
    ;;
  record-soak)
    chmod +x "$ROOT/scripts/wave1_leads_soak_record.sh"
    "$ROOT/scripts/wave1_leads_soak_record.sh"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    echo "Usage: $0 {preflight|bootstrap-soak|full|signoff|record-soak}" >&2
    exit 2
    ;;
esac
