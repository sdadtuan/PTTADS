#!/usr/bin/env bash
# Wave B5 S0 — contract promote bridge deploy
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"

echo "== Wave B5 S0 deploy =="
echo "ROOT=$ROOT"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"
echo "Required env: PTT_CRM_SERVICE_DELIVERY_NEST=1 PTT_CRM_LEADS_FUNNEL_NEST=1 PTT_PRESALES_ON_LEAD=1"

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
      if [[ "${WAVE_B5_S0_UPDATE_ENV:-0}" == "1" ]]; then
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        echo "UPD  $key"
      fi
    else
      echo "$line" >>"$ENV_FILE"
      echo "ADD  $line"
    fi
  done <<<"$block"
}

if [[ "${WAVE_B5_S0_UPDATE_ENV:-0}" == "1" ]]; then
  merge_env_block "PTT_CRM_SERVICE_DELIVERY_NEST=1
PTT_CRM_LEADS_FUNNEL_NEST=1
PTT_PRESALES_ON_LEAD=1"
fi

echo "-- Nest ptt-crm-api --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

if grep -q "LeadsContractModule" dist/app.module.js 2>/dev/null; then
  echo "OK  LeadsContractModule in dist"
else
  echo "FAIL LeadsContractModule missing from build"
  exit 1
fi

if [[ -f dist/leads-contract/lifecycle-workflow-steps.data.json ]]; then
  echo "OK  lifecycle workflow JSON in dist"
else
  echo "WARN  copy lifecycle-workflow-steps.data.json to dist"
  mkdir -p dist/leads-contract
  cp src/leads-contract/lifecycle-workflow-steps.data.json dist/leads-contract/ 2>/dev/null || true
fi

echo "-- ops-web --"
cd "$ROOT/services/ops-web"
npm ci
export NEXT_PUBLIC_PTT_API_URL="$OPS_API_URL"
npm run build
mkdir -p .next/standalone/.next
rm -rf .next/standalone/.next/static
cp -r .next/static .next/standalone/.next/static
if [[ -d public ]]; then
  rm -rf .next/standalone/public
  cp -r public .next/standalone/public
fi

echo "-- gate --"
bash "$ROOT/scripts/wave_b5_s0_gate.sh"

echo "-- restart services --"
for svc in ptt-crm-api ptt-ops-web; do
  if systemctl restart "$svc" 2>/dev/null; then
    echo "OK  restarted $svc"
  else
    echo "WARN  could not restart $svc — run: sudo systemctl restart $svc"
  fi
done

sleep 2
if curl -sf "http://127.0.0.1:3000/health" >/dev/null; then
  code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/contracts/approvals/pending")"
  if [[ "$code" == "401" || "$code" == "403" ]]; then
    echo "OK  GET contracts/approvals/pending (HTTP $code)"
  elif [[ "$code" == "404" ]]; then
    body="$(curl -s "http://127.0.0.1:3000/api/v1/contracts/approvals/pending")"
    if [[ "$body" == *"PTT_CRM_SERVICE_DELIVERY_NEST"* || "$body" == *"Wave B5"* ]]; then
      echo "FAIL Wave B5 disabled — set PTT_CRM_SERVICE_DELIVERY_NEST=1 in .env and restart"
      exit 1
    fi
    echo "FAIL missing Wave B5 routes"
    exit 1
  fi
fi

echo ""
echo "Next:"
echo "  WAVE_B5_S0_UPDATE_ENV=1 ./scripts/wave_b5_s0_deploy.sh   # merge env flags"
echo "  sudo systemctl restart ptt-crm-api ptt-ops-web"
echo "  ADMIN_PASSWORD='...' ./scripts/wave_b5_s0_smoke.sh"
