#!/usr/bin/env bash
# Wave B2.5 — Hub campaign map CRUD (Agency-native PG provisioning).
# Run as deploy from repo root: ./scripts/wave_b25_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"

echo "== Wave B2.5 deploy =="
echo "ROOT=$ROOT"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"

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
restart_ok=1
for svc in ptt-crm-api ptt-ops-web; do
  if systemctl restart "$svc" 2>/dev/null; then
    echo "OK  restarted $svc"
  else
    echo "WARN  could not restart $svc — run: sudo systemctl restart $svc"
    restart_ok=0
  fi
done

if [[ "$restart_ok" -eq 1 ]]; then
  sleep 2
  curl -sf "http://127.0.0.1:3000/health" >/dev/null && echo "OK  Nest /health"
  hub_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:3000/api/v1/crm/hub-campaign-maps" \
    -H 'Content-Type: application/json' -d '{}')"
  if [[ "$hub_code" == "401" || "$hub_code" == "403" || "$hub_code" == "400" ]]; then
    echo "OK  POST hub-campaign-maps route present (HTTP $hub_code)"
  elif [[ "$hub_code" == "404" || "$hub_code" == "405" ]]; then
    echo "FAIL Nest thiếu Wave B2.5 POST — rebuild + restart ptt-crm-api"
    exit 1
  fi
fi

echo ""
echo "Next: ADMIN_PASSWORD='...' CLIENT_ID=<uuid> ./scripts/wave_b25_smoke.sh"
echo "UI:  /agency/clients/<id>?tab=campaigns  ·  /crm/hub"
