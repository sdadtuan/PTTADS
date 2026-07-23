#!/usr/bin/env bash
# Wave B4 — CRM lead funnel (B2 care + review queue + presales on Nest).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"

echo "== Wave B4 deploy =="
echo "ROOT=$ROOT"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"
echo "Env: PTT_CRM_LEADS_FUNNEL_NEST=1 PTT_PRESALES_ON_LEAD=1"

echo "-- export presales workflow steps (from Python source of truth) --"
python3 "$ROOT/scripts/export_presales_workflow_steps.py"

echo "-- optional PG DDL (S0 prep, does not switch Nest store) --"
if [[ "${WAVE_B4_APPLY_PG_DDL:-0}" == "1" ]]; then
  bash "$ROOT/scripts/apply_pg_ddl_wave_b4_funnel.sh"
else
  echo "SKIP PG DDL (set WAVE_B4_APPLY_PG_DDL=1 to apply)"
fi

echo "-- Nest ptt-crm-api --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

if [[ -f dist/leads-funnel/presales-workflow-steps.data.json ]]; then
  echo "OK  workflow steps JSON in dist"
else
  echo "WARN  missing dist/leads-funnel/presales-workflow-steps.data.json"
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

echo "-- review queue cron units (install with sudo on VPS) --"
if [[ -f "$ROOT/deploy/ptt-lead-review-queue-sync.timer" ]]; then
  echo "OK  deploy/ptt-lead-review-queue-sync.{service,timer} present"
  echo "     sudo cp deploy/ptt-lead-review-queue-sync.* /etc/systemd/system/"
  echo "     sudo systemctl daemon-reload && sudo systemctl enable --now ptt-lead-review-queue-sync.timer"
fi

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
  echo "OK  Nest /health"
  code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/leads/review-queue/count")"
  if [[ "$code" == "401" || "$code" == "403" ]]; then
    echo "OK  GET review-queue/count route present (HTTP $code)"
  elif [[ "$code" == "404" ]]; then
    body="$(curl -s "http://127.0.0.1:3000/api/v1/leads/review-queue/count")"
    if [[ "$body" == *"PTT_CRM_LEADS_FUNNEL_NEST"* ]]; then
      echo "WARN funnel disabled — set PTT_CRM_LEADS_FUNNEL_NEST=1 in .env"
    else
      echo "FAIL missing Wave B4 routes"
      exit 1
    fi
  fi
  sync_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:3000/api/v1/leads/review-queue/sync" -H 'Content-Type: application/json' -d '{}')"
  if [[ "$sync_code" == "401" || "$sync_code" == "403" ]]; then
    echo "OK  POST review-queue/sync route present (HTTP $sync_code)"
  else
    echo "WARN POST review-queue/sync HTTP $sync_code (expect 401 without internal key)"
  fi
fi

echo ""
echo "Next:"
echo "  sudo systemctl restart ptt-crm-api ptt-ops-web   # if deploy user could not restart"
echo "  ADMIN_PASSWORD='...' LEAD_ID=<id> ./scripts/wave_b4_smoke.sh"
echo "  ./scripts/wave_b4_gate.sh                          # DoD gate (pytest + Nest)"
echo "  WAVE_B4_APPLY_PG_DDL=1 ./scripts/wave_b4_deploy.sh  # apply PG DDL on VPS"
