#!/bin/sh
# Gọi cron cảnh báo KPI finance — Slack/email + inbox CRM.
set -eu

APP_DIR="${PTT_APP_DIR:-/var/www/ptt}"
HOST="${PTT_SYNC_HOST:-127.0.0.1}"
DOMAIN="${PTT_SYNC_DOMAIN:-pttads.vn}"
PUBLIC_BASE="${PTT_SYNC_PUBLIC_URL:-https://pttads.vn}"
PATH_SUFFIX="/api/crm/finance/kpi-alert-cron"

env_get() {
  _key="$1"
  _default="${2:-}"
  eval "_cur=\${${_key}:-}"
  if [ -n "$_cur" ]; then
    printf '%s' "$_cur"
    return 0
  fi
  _file="$APP_DIR/.env"
  [ -f "$_file" ] || {
    printf '%s' "$_default"
    return 0
  }
  _line=$(grep -E "^[[:space:]]*${_key}=" "$_file" 2>/dev/null | grep -v '^[[:space:]]*#' | tail -1) || true
  if [ -z "$_line" ]; then
    printf '%s' "$_default"
    return 0
  fi
  _val=${_line#*=}
  case "$_val" in
    \"*) _val=${_val#\"}; _val=${_val%\"} ;;
    \'*) _val=${_val#\'}; _val=${_val%\'} ;;
  esac
  printf '%s' "$_val"
}

SECRET=$(env_get CRM_FINANCE_KPI_CRON_SECRET "")
if [ -z "$SECRET" ]; then
  SECRET=$(env_get CRM_FACEBOOK_SYNC_SECRET "")
fi
if [ -z "$SECRET" ]; then
  SECRET=$(env_get CRM_MARKETING_INGEST_SECRET "")
fi

PTT_SYNC_URL=$(env_get PTT_SYNC_URL "")
PTT_GUNICORN_PORT=$(env_get PTT_GUNICORN_PORT "8002")
ONLY_CRITICAL=$(env_get PTT_FINANCE_KPI_ALERT_ONLY_CRITICAL "1")

probe_ok() {
  _url="$1"
  shift
  /usr/bin/curl -fsS --max-time 12 "$@" "$_url" >/dev/null 2>&1
}

SYNC_URL=""
USE_NGINX_HOST=0

if [ -n "$PTT_SYNC_URL" ]; then
  case "$PTT_SYNC_URL" in
    *kpi-alert-cron*) SYNC_URL="$PTT_SYNC_URL" ;;
    *) SYNC_URL="${PTT_SYNC_URL%/}${PATH_SUFFIX}" ;;
  esac
else
  for PORT in $PTT_GUNICORN_PORT 8002 5050; do
    [ -n "$PORT" ] || continue
    if probe_ok "http://${HOST}:${PORT}/healthz"; then
      SYNC_URL="http://${HOST}:${PORT}${PATH_SUFFIX}"
      break
    fi
  done
  if [ -z "$SYNC_URL" ]; then
    for PORT in 80 8080; do
      if probe_ok "http://${HOST}:${PORT}/healthz" -H "Host: ${DOMAIN}"; then
        SYNC_URL="http://${HOST}:${PORT}${PATH_SUFFIX}"
        USE_NGINX_HOST=1
        break
      fi
    done
  fi
  if [ -z "$SYNC_URL" ]; then
    BASE="${PUBLIC_BASE%/}"
    if probe_ok "${BASE}/healthz"; then
      SYNC_URL="${BASE}${PATH_SUFFIX}"
    fi
  fi
fi

if [ -z "$SYNC_URL" ]; then
  echo "ptt_finance_kpi_alert_cron: không gọi được /healthz." >&2
  exit 1
fi

if [ "$ONLY_CRITICAL" = "0" ]; then
  CRIT_JSON="false"
else
  CRIT_JSON="true"
fi

if [ "$USE_NGINX_HOST" -eq 1 ]; then
  if [ -n "$SECRET" ]; then
    exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
      -H "Content-Type: application/json" \
      -H "Host: ${DOMAIN}" \
      -H "Authorization: Bearer ${SECRET}" \
      -d "{\"only_critical\":${CRIT_JSON}}"
  fi
  exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
    -H "Content-Type: application/json" \
    -H "Host: ${DOMAIN}" \
    -d "{\"only_critical\":${CRIT_JSON}}"
fi

if [ -n "$SECRET" ]; then
  exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${SECRET}" \
    -d "{\"only_critical\":${CRIT_JSON}}"
fi

exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
  -H "Content-Type: application/json" \
  -d "{\"only_critical\":${CRIT_JSON}}"
