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
  probe_post_route() {
    local label="$1"
    local url="$2"
    local body code
    body="$(curl -s -X POST "$url" -H 'Content-Type: application/json' -d '{}')"
    code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" -H 'Content-Type: application/json' -d '{}')"
    if [[ "$body" == *"Cannot POST"* ]]; then
      echo "FAIL Nest thiếu Wave B2.5 $label (HTTP $code route missing)"
      return 1
    fi
    echo "OK  POST $label route present (HTTP $code)"
    return 0
  }
  probe_post_route "crm/hub-campaign-maps" "http://127.0.0.1:3000/api/v1/crm/hub-campaign-maps"
  probe_post_route "clients/:id/hub-campaign-maps" \
    "http://127.0.0.1:3000/api/v1/clients/00000000-0000-0000-0000-000000000001/hub-campaign-maps"
fi

echo ""
echo "Next: ADMIN_PASSWORD='...' CLIENT_ID=<uuid> ./scripts/wave_b25_smoke.sh"
echo "UI:  /agency/clients/<id>?tab=campaigns  ·  /crm/hub"
