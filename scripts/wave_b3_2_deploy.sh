#!/usr/bin/env bash
# Wave B3.2 — Meta hub UAT filters + CSV export (ops-web + Nest).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Wave B3.2 deploy (Meta hub filters + export) =="

echo "-- Nest ptt-crm-api --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

echo "-- ops-web --"
cd "$ROOT/services/ops-web"
npm ci
export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
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
    echo "WARN  could not restart $svc"
  fi
done

sleep 2
hub_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/facebook-ads/hub?days=7")"
exp_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/facebook-ads/hub/export?days=7")"
if [[ "$hub_code" == "401" || "$hub_code" == "403" ]]; then
  echo "OK  GET facebook-ads/hub route (HTTP $hub_code)"
elif [[ "$hub_code" == "200" ]]; then
  echo "OK  GET facebook-ads/hub (HTTP 200)"
else
  echo "WARN  GET facebook-ads/hub HTTP $hub_code"
fi
if [[ "$exp_code" == "401" || "$exp_code" == "403" ]]; then
  echo "OK  GET facebook-ads/hub/export route (HTTP $exp_code)"
else
  echo "WARN  GET export HTTP $exp_code"
fi

echo ""
echo "Next: ADMIN_PASSWORD='...' ./scripts/wave_b3_2_smoke.sh"
echo "UI: /meta/facebook-ads"
