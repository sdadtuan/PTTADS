#!/usr/bin/env bash
# Wave B2 — build Nest side effects + ops-web workflow UI on VPS.
# Run as deploy from repo root: ./scripts/wave_b2_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"

echo "== Wave B2 deploy =="
echo "ROOT=$ROOT"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "WARN: $ROOT/.env missing — Nest needs DATABASE_URL, PTT_JOBS_ENABLED, PTT_TOKEN_VAULT_KEY"
fi

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

echo "-- restart services (needs permission) --"
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
  curl -sf -o /dev/null "http://127.0.0.1:3200/login" && echo "OK  ops-web :3200"
  leads_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/clients")"
  if [[ "$leads_code" == "401" || "$leads_code" == "403" ]]; then
    echo "OK  Nest Wave B2 routes present (clients HTTP $leads_code — auth required)"
  elif [[ "$leads_code" == "404" ]]; then
    echo "FAIL Nest thiếu Wave B2 — dist cũ? Chạy lại npm run build && sudo systemctl restart ptt-crm-api"
    exit 1
  fi
fi

echo ""
echo "Next: ADMIN_PASSWORD='...' ./scripts/wave_b2_smoke.sh"
echo "UI:  https://rs.pttads.vn/agency/clients/<id>?tab=leads"
