#!/usr/bin/env bash
# Wave B5 full deploy — S0 promote bridge + S1–S5 lifecycle/tasks/TMMT/finance/SOP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"

echo "== Wave B5 full deploy =="
echo "ROOT=$ROOT"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"

merge_env_block() {
  local block="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "WARN  $ENV_FILE missing — merge env manually from deploy/env.crm-flask-migration.example"
    return 0
  fi
  while IFS= read -r line; do
    [[ "$line" =~ ^# ]] && continue
    [[ -z "${line// /}" ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
      if [[ "${WAVE_B5_UPDATE_ENV:-0}" == "1" ]]; then
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        echo "UPD  $key"
      fi
    else
      echo "$line" >>"$ENV_FILE"
      echo "ADD  $line"
    fi
  done <<<"$block"
}

if [[ "${WAVE_B5_UPDATE_ENV:-0}" == "1" ]]; then
  merge_env_block "PTT_CRM_SERVICE_DELIVERY_NEST=1
PTT_CRM_LEADS_FUNNEL_NEST=1
PTT_PRESALES_ON_LEAD=1
PTT_SOP_AUTO_START_ON_LAUNCH=1
PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED=1
WAVE_B5_EXPECT_SERVICE_DELIVERY_NEST=1"
fi

echo "-- S0 deploy base --"
WAVE_B5_S0_UPDATE_ENV=0 bash "$ROOT/scripts/wave_b5_s0_deploy.sh"

echo "-- gate --"
export PTT_CRM_SERVICE_DELIVERY_NEST=1
export PTT_CRM_LEADS_FUNNEL_NEST=1
export PTT_PRESALES_ON_LEAD=1
bash "$ROOT/scripts/wave_b5_gate.sh" || {
  echo "WARN gate failed locally — kiểm tra trên VPS sau restart"
}

echo ""
echo "UAT manual (PO sign-off): docs/runbooks/wave-b5-po-signoff-checklist.md"
echo "  ADMIN_PASSWORD='...' ./scripts/wave_b5_s0_smoke.sh"
echo "  ADMIN_PASSWORD='...' ./scripts/wave_b5_smoke.sh"
echo "  ./scripts/wave_b5_pytest_parity.sh"
