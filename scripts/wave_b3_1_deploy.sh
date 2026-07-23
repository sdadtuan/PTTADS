#!/usr/bin/env bash
# Wave B3.1 — Meta webhook Nest-only (Horizon 1 M1-B1).
# Run as deploy from repo root: ./scripts/wave_b3_1_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"

echo "== Wave B3.1 deploy (Meta webhook Nest) =="
echo "ROOT=$ROOT"
echo "ENV_FILE=$ENV_FILE"

required_vars=(
  PTT_WEBHOOKS_NEST_ENABLED
  PTT_WEBHOOKS_NEST_META
  PTT_WEBHOOKS_FLASK_FALLBACK
  PTT_JOBS_ENABLED
  CRM_FACEBOOK_VERIFY_TOKEN
)

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

warn=0
for v in "${required_vars[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "WARN  thiếu $v trong $ENV_FILE"
    warn=1
  fi
done
if [[ "${PTT_WEBHOOKS_FLASK_FALLBACK:-}" != "0" ]]; then
  echo "WARN  PTT_WEBHOOKS_FLASK_FALLBACK nên = 0 cho cutover Nest-only"
  warn=1
fi
[[ "$warn" -eq 0 ]] && echo "OK  webhook env flags present"

echo "-- Nest ptt-crm-api --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

echo "-- nginx webhook upstream (nest-meta) --"
if [[ -x "$ROOT/scripts/apply_webhooks_upstream.sh" ]]; then
  if sudo "$ROOT/scripts/apply_webhooks_upstream.sh" nest-meta; then
    echo "OK  nginx nest-meta routing"
  else
    echo "WARN  nginx apply failed — chạy thủ công: sudo ./scripts/apply_webhooks_upstream.sh nest-meta"
  fi
else
  echo "WARN  missing apply_webhooks_upstream.sh"
fi

echo "-- restart ptt-crm-api --"
if systemctl restart ptt-crm-api 2>/dev/null; then
  sleep 2
  curl -sf "http://127.0.0.1:3000/health" >/dev/null && echo "OK  Nest /health"
  ch_code="$(curl -s -o /dev/null -w "%{http_code}" \
    "http://127.0.0.1:3000/api/v1/webhooks/meta?hub.mode=subscribe&hub.verify_token=${CRM_FACEBOOK_VERIFY_TOKEN:-missing}&hub.challenge=b31")"
  if [[ "$ch_code" == "200" ]]; then
    echo "OK  GET meta hub challenge (HTTP 200)"
  else
    echo "WARN  hub challenge HTTP $ch_code — kiểm tra CRM_FACEBOOK_VERIFY_TOKEN"
  fi
else
  echo "WARN  could not restart ptt-crm-api — sudo systemctl restart ptt-crm-api"
fi

echo ""
echo "Next: ./scripts/wave_b3_1_smoke.sh"
echo "Meta Developer Console webhook URL: ${OPS_API_URL}/api/v1/webhooks/meta"
echo "Runbook: docs/runbooks/wave-b3.1-meta-webhook-nest.md"
