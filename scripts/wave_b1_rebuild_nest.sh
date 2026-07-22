#!/usr/bin/env bash
# Rebuild + restart Nest only (Wave B1 API routes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/services/ptt-crm-api"
echo "== Rebuild ptt-crm-api =="
git -C "$ROOT" log -1 --oneline
npm ci
npm run build
if systemctl restart ptt-crm-api 2>/dev/null; then
  echo "OK  restarted ptt-crm-api"
else
  echo "Run: sudo systemctl restart ptt-crm-api"
  exit 1
fi
sleep 2
code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3000/api/v1/kpi-definitions")"
echo "probe GET /api/v1/kpi-definitions → HTTP $code"
if [[ "$code" == "404" ]]; then
  echo "FAIL  dist vẫn thiếu route — kiểm tra git pull (cần commit Wave B1 trên main)"
  exit 1
fi
echo "OK  Wave B1 Nest routes loaded (401/403 = expected without token)"
