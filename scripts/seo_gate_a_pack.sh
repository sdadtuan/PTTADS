#!/usr/bin/env bash
# SEO Gate A pack — preflight, soak record, evaluate, full (Phase 7).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
MODE="${1:-preflight}"
ENV_EXAMPLE="$ROOT/deploy/env.seo-gate-a-prod.example"

case "$MODE" in
  preflight)
    echo "==> Gate A preflight (wave B7 + phase5, soak skipped)"
    export PHASE5_SKIP_SOAK=1
    export PHASE5_SKIP_PORTAL_SIGNOFF=1
    bash "$ROOT/scripts/seo_gate_a_cutover_gate.sh"
    ;;
  soak)
    echo "==> Record soak snapshot"
    bash "$ROOT/scripts/phase5_soak_record.sh"
    ;;
  evaluate)
    echo "==> Evaluate soak + gate reports"
    export PHASE5_SKIP_SOAK=0
    export PHASE5_SKIP_PORTAL_SIGNOFF="${PHASE5_SKIP_PORTAL_SIGNOFF:-1}"
    bash "$ROOT/scripts/seo_gate_a_cutover_gate.sh"
    ;;
  full)
    echo "==> Gate A full pack"
    export PHASE5_SKIP_SOAK=1
    bash "$ROOT/scripts/seo_gate_a_cutover_gate.sh"
    bash "$ROOT/scripts/phase5_soak_record.sh" || true
    export PHASE5_SKIP_SOAK=0
    bash "$ROOT/scripts/seo_gate_a_cutover_gate.sh"
    ;;
  *)
    echo "Usage: $0 {preflight|soak|evaluate|full}" >&2
    exit 2
    ;;
esac

echo ""
echo "Env example: $ENV_EXAMPLE"
echo "Sign-off template: docs/evidence/seo-gate-a-signoff.template.json"
if [[ -f "$PTT_ARTIFACTS_DIR/wave-gates/seo_b7_gate_report.json" ]]; then
  echo "B7 report: $PTT_ARTIFACTS_DIR/wave-gates/seo_b7_gate_report.json"
fi
