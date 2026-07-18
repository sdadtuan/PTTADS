#!/usr/bin/env bash
# SLA sync cron — gọi /api/crm/agency/sla-sync-cron mỗi 5 phút (Phase 1 E6)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/.local-dev"
mkdir -p "$LOG_DIR"

PORT="${PORT:-5050}"
BASE="http://127.0.0.1:$PORT"
INTERVAL="${PTT_SLA_CRON_INTERVAL_SEC:-300}"
SECRET="${CRM_AGENCY_SLA_CRON_SECRET:-}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
  SECRET="${CRM_AGENCY_SLA_CRON_SECRET:-$SECRET}"
fi

_url="${BASE}/api/crm/agency/sla-sync-cron"
if [[ -n "$SECRET" ]]; then
  _url="${_url}?secret=${SECRET}"
fi

echo "==> SLA cron loop every ${INTERVAL}s → $_url"
while true; do
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if curl -sf -X POST "$_url" -H "X-Cron-Secret: ${SECRET}" >>"$LOG_DIR/sla_cron.log" 2>&1; then
    echo "[$ts] SLA sync OK" >>"$LOG_DIR/sla_cron.log"
  else
    echo "[$ts] SLA sync FAIL (is Flask up?)" >>"$LOG_DIR/sla_cron.log"
  fi
  sleep "$INTERVAL"
done
