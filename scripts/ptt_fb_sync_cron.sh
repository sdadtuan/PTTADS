#!/bin/sh
# Gọi sync-cron Facebook Lead — dùng trong ptt-fb-sync.service (systemd)
# POSIX sh (dash) — không dùng bash arrays.
set -eu

APP_DIR="${PTT_APP_DIR:-/var/www/ptt}"
HOST="${PTT_SYNC_HOST:-127.0.0.1}"
DOMAIN="${PTT_SYNC_DOMAIN:-pttads.vn}"
PUBLIC_BASE="${PTT_SYNC_PUBLIC_URL:-https://pttads.vn}"
PATH_SUFFIX="/api/crm/integration/facebook/sync-cron"

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

SECRET=$(env_get CRM_FACEBOOK_SYNC_SECRET "")
if [ -z "$SECRET" ]; then
  SECRET=$(env_get CRM_MARKETING_INGEST_SECRET "")
fi

PTT_SYNC_URL=$(env_get PTT_SYNC_URL "")
PTT_NEST_API_URL=$(env_get PTT_NEST_API_URL "")

probe_ok() {
  _url="$1"
  shift
  /usr/bin/curl -fsS --max-time 12 "$@" "$_url" >/dev/null 2>&1
}

SYNC_URL=""
USE_NGINX_HOST=0

if [ -n "$PTT_SYNC_URL" ]; then
  SYNC_URL="$PTT_SYNC_URL"
else
  NEST_BASE="${PTT_NEST_API_URL:-http://${HOST}:3000}"
  NEST_BASE="${NEST_BASE%/}"
  if probe_ok "${NEST_BASE}/health"; then
    SYNC_URL="${NEST_BASE}${PATH_SUFFIX}"
  fi

  if [ -z "$SYNC_URL" ]; then
    for PORT in 80 8080; do
      if probe_ok "http://${HOST}:${PORT}/health" -H "Host: ${DOMAIN}"; then
        SYNC_URL="http://${HOST}:${PORT}${PATH_SUFFIX}"
        USE_NGINX_HOST=1
        break
      fi
    done
  fi

  if [ -z "$SYNC_URL" ]; then
    BASE="${PUBLIC_BASE%/}"
    if probe_ok "${BASE}/health"; then
      SYNC_URL="${BASE}${PATH_SUFFIX}"
    fi
  fi
fi

if [ -z "$SYNC_URL" ]; then
  echo "ptt_fb_sync_cron: không gọi được Nest /health." >&2
  echo "Kiểm tra: systemctl status ptt-crm-api | journalctl -u ptt-crm-api -n 30" >&2
  echo "Gợi ý .env: PTT_SYNC_URL=https://pttads.vn${PATH_SUFFIX}" >&2
  exit 1
fi

USE_LOCAL=0
case "$SYNC_URL" in
  http://127.0.0.1:*|http://localhost:*)
    USE_LOCAL=1
    ;;
esac

if [ -z "$SECRET" ] && [ "$USE_LOCAL" -eq 0 ] && [ "$USE_NGINX_HOST" -eq 0 ]; then
  case "$SYNC_URL" in
    https://*) ;;
    *) USE_LOCAL=1 ;;
  esac
fi

if [ -z "$SECRET" ] && [ "$USE_LOCAL" -eq 0 ]; then
  echo "ptt_fb_sync_cron: cần CRM_FACEBOOK_SYNC_SECRET khi gọi qua HTTPS/Nginx." >&2
  exit 1
fi

if [ "$USE_NGINX_HOST" -eq 1 ]; then
  exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
    -H "Content-Type: application/json" \
    -H "Host: ${DOMAIN}" \
    -H "Authorization: Bearer ${SECRET}" \
    -d "{}"
fi

if [ -n "$SECRET" ]; then
  exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${SECRET}" \
    -d "{}"
fi

exec /usr/bin/curl -fsS --max-time 120 -X POST "$SYNC_URL" \
  -H "Content-Type: application/json" \
  -d "{}"
