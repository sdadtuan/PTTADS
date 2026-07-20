#!/usr/bin/env bash
# Phase 2 Agency prod cutover — gate pack → apply_phase2_cutover
#
# Usage (on VPS after sourcing deploy/env.phase2-prod.example):
#   ./scripts/phase2_prod_cutover.sh              # gate + dry-run cutover
#   ./scripts/phase2_prod_cutover.sh --apply      # gate + nginx/env cutover + reload
#   ./scripts/phase2_prod_cutover.sh --gate-only  # skip cutover script
#   ./scripts/phase2_prod_cutover.sh --skip-gate  # cutover only (dangerous)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPLY=0
GATE_ONLY=0
SKIP_GATE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --gate-only) GATE_ONLY=1 ;;
    --skip-gate) SKIP_GATE=1 ;;
    -h|--help)
      echo "Usage: phase2_prod_cutover.sh [--apply] [--gate-only] [--skip-gate]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

export DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-/var/www/ptt/ptt.db}"
export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_LEADS_WRITE_SOURCE="${PTT_LEADS_WRITE_SOURCE:-pg}"
export PTT_LEAD_SHADOW_SYNC="${PTT_LEAD_SHADOW_SYNC:-1}"
export PTT_LEAD_INGEST_RULES_SOURCE="${PTT_LEAD_INGEST_RULES_SOURCE:-pg}"
export PTT_META_INSIGHTS_SYNC="${PTT_META_INSIGHTS_SYNC:-1}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase2-prod-cutover-report.json"

if [[ "$SKIP_GATE" -eq 0 ]]; then
  echo "==> Phase 2 prod gate pack"
  if ! "$ROOT/scripts/staging_phase2_gate_pack.sh" \
    --skip-soak \
    --report "$REPORT"; then
    echo "FAIL Phase 2 gate pack — fix before cutover" >&2
    exit 1
  fi
  echo "OK  Gate report: $REPORT"
fi

if [[ "$GATE_ONLY" -eq 1 ]]; then
  echo "OK  Gate-only mode — skipping apply_phase2_cutover"
  exit 0
fi

echo ""
if [[ "$APPLY" -eq 1 ]]; then
  echo "==> Applying Phase 2 cutover (nginx + ingest sync)"
  sudo "$ROOT/scripts/apply_phase2_cutover.sh" --reload
  echo ""
  echo "==> Post-cutover checklist"
  echo "  1. systemctl restart ptt-crm-api ptt-worker ops-web"
  echo "  2. ./scripts/install_phase2_systemd_timers.sh  (shadow sync timer)"
  echo "  3. ./scripts/sync_hub_campaign_map.sh"
  echo "  4. ./scripts/sync_meta_insights.sh"
  echo "  5. Verify ops.pttads.vn/agency + /crm/hub"
else
  echo "==> Dry-run Phase 2 cutover (pass --apply to execute on VPS)"
  "$ROOT/scripts/apply_phase2_cutover.sh" --dry-run
fi

echo ""
echo "OK  Phase 2 prod cutover flow complete"
