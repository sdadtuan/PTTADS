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

echo "-- Nest ptt-crm-api --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

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
fi

echo ""
echo "Next: ADMIN_PASSWORD='...' LEAD_ID=<id> ./scripts/wave_b4_smoke.sh"
echo "Cron: sudo cp deploy/ptt-lead-review-queue-sync.* /etc/systemd/system/ && sudo systemctl enable --now ptt-lead-review-queue-sync.timer"
