#!/usr/bin/env bash
# CRM Flask retirement — orchestrator (Wave 0 → Phase 5)
#
# Usage:
#   ./scripts/crm_flask_migration_pack.sh gap        # module gap report
#   ./scripts/crm_flask_migration_pack.sh wave0      # apply Wave 0 env checks + Horizon packs
#   ./scripts/crm_flask_migration_pack.sh gates      # CRM retirement gates
#   ./scripts/crm_flask_migration_pack.sh wave1-catalog  # Wave 1 catalog gates
#   ./scripts/crm_flask_migration_pack.sh wave1b-leads    # Wave 1b leads legacy gates
#   ./scripts/crm_flask_migration_pack.sh wave1-full      # Wave 1 full (catalog + leads UI)
#   ./scripts/crm_flask_migration_pack.sh wave2           # Wave 2 customers + intake gates
#   ./scripts/crm_flask_migration_pack.sh wave2-plus      # Wave 2+ extended + cases
#   ./scripts/crm_flask_migration_pack.sh wave3           # Wave 3 service ops
#   ./scripts/crm_flask_migration_pack.sh wave4           # Wave 4 sales + KPI + staff
#   ./scripts/crm_flask_migration_pack.sh wave4-plus      # Wave 4+ extended + proposals
#   ./scripts/crm_flask_migration_pack.sh wave5           # Wave 5 RE projects + payroll
#   ./scripts/crm_flask_migration_pack.sh wave5-plus      # Wave 5+ RE accounting
#   ./scripts/crm_flask_migration_pack.sh wave5-pp        # Wave 5++ RE KPI/risks/budget
#   ./scripts/crm_flask_migration_pack.sh wave5-ppp       # Wave 5+++ RE staff/lead/workflow/export
#   ./scripts/crm_flask_migration_pack.sh wave6           # Wave 6 finance / owner-weekly
#   ./scripts/crm_flask_migration_pack.sh wave7           # Wave 7 Phase 5 readiness
#   ./scripts/crm_flask_migration_pack.sh wave8           # Wave 8 Flask HTTP removed
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

ENV_EXAMPLE="$ROOT/deploy/env.crm-flask-migration.example"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

MODE="${1:-gap}"

case "$MODE" in
  gap)
    "$PYTHON" -m ptt_crm.crm_flask_retirement_registry
    ;;
  gates)
    "$PYTHON" -m ptt_crm.crm_flask_retirement_gates
    ;;
  wave0)
    echo "==> Wave 0 — partial CRM cutover (leads/agency/webhooks/delivery-admin)"
    chmod +x "$ROOT/scripts/horizon0_gate_a_pack.sh" "$ROOT/scripts/horizon1_meta_ads_pack.sh" 2>/dev/null || true
    HORIZON1_SKIP_SOAK=1 HORIZON1_SKIP_NEST_SMOKE=1 "$ROOT/scripts/horizon1_meta_ads_pack.sh" preflight || true
    EM5_SKIP_SOAK=1 PHASE5DA_SKIP_BUILD=1 "$ROOT/scripts/horizon0_gate_a_pack.sh" preflight 2>/dev/null || true
    "$PYTHON" -m ptt_crm.crm_flask_retirement_gates
    echo ""
    echo "Wave 0 complete. Flask vẫn chạy cho: catalog, customers, staff, SOP, RE, ..."
    ;;
  phase5-dry)
    echo "==> Phase 5 dry-run (stop ptt.service) — chỉ PASS khi 100% module migrated"
    export CRM_FLASK_REQUIRE_FULL_MIGRATION=1
    export CRM_SKIP_PHASE5_PREREQ=0
    "$PYTHON" -m ptt_crm.crm_flask_retirement_registry || true
    "$PYTHON" -m ptt_crm.crm_flask_retirement_gates || true
    chmod +x "$ROOT/scripts/close_flask_retirement.sh"
    APPLY=0 "$ROOT/scripts/close_flask_retirement.sh" || true
    ;;
  wave1-catalog)
    chmod +x "$ROOT/scripts/wave1_catalog_gate.sh"
    "$ROOT/scripts/wave1_catalog_gate.sh"
    ;;
  wave1b-leads)
    chmod +x "$ROOT/scripts/wave1b_leads_gate.sh"
    "$ROOT/scripts/wave1b_leads_gate.sh"
    ;;
  wave1-full)
    chmod +x "$ROOT/scripts/wave1_full_pack.sh"
    "$ROOT/scripts/wave1_full_pack.sh" preflight
    ;;
  wave2)
    chmod +x "$ROOT/scripts/wave2_gate.sh"
    "$ROOT/scripts/wave2_gate.sh"
    ;;
  wave2-plus)
    chmod +x "$ROOT/scripts/wave2_plus_gate.sh"
    "$ROOT/scripts/wave2_plus_gate.sh"
    ;;
  wave3)
    chmod +x "$ROOT/scripts/wave3_gate.sh"
    "$ROOT/scripts/wave3_gate.sh"
    ;;
  wave4)
    chmod +x "$ROOT/scripts/wave4_gate.sh"
    "$ROOT/scripts/wave4_gate.sh"
    ;;
  wave4-plus)
    chmod +x "$ROOT/scripts/wave4_plus_gate.sh"
    "$ROOT/scripts/wave4_plus_gate.sh"
    ;;
  wave5)
    chmod +x "$ROOT/scripts/wave5_gate.sh"
    "$ROOT/scripts/wave5_gate.sh"
    ;;
  wave5-plus)
    chmod +x "$ROOT/scripts/wave5_plus_gate.sh"
    "$ROOT/scripts/wave5_plus_gate.sh"
    ;;
  wave5-pp)
    chmod +x "$ROOT/scripts/wave5_pp_gate.sh"
    "$ROOT/scripts/wave5_pp_gate.sh"
    ;;
  wave5-ppp)
    chmod +x "$ROOT/scripts/wave5_ppp_gate.sh"
    "$ROOT/scripts/wave5_ppp_gate.sh"
    ;;
  wave6)
    chmod +x "$ROOT/scripts/wave6_gate.sh"
    "$ROOT/scripts/wave6_gate.sh"
    ;;
  wave7)
    chmod +x "$ROOT/scripts/wave7_gate.sh"
    "$ROOT/scripts/wave7_gate.sh"
    ;;
  wave8)
    chmod +x "$ROOT/scripts/wave8_gate.sh"
    "$ROOT/scripts/wave8_gate.sh"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
