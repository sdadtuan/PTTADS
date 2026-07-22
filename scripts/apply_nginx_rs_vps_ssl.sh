#!/usr/bin/env bash
# Install rs.pttads.vn nginx site using /etc/nginx/ssl certs + ops-web static alias.
#   sudo ./scripts/apply_nginx_rs_vps_ssl.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Usage: sudo $0"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/nginx_ssl_paths.sh
. "$ROOT/scripts/lib/nginx_ssl_paths.sh"

DEST="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"
SRC="$ROOT/deploy/nginx-rs-flask-retired.conf"
DOMAIN="rs.pttads.vn"

if [[ -f "$DEST" ]]; then
  cp "$DEST" "${DEST}.bak.$(date +%Y%m%d%H%M%S)"
fi

cp "$SRC" "$DEST"
nginx_ssl_rewrite_site "$DEST" "$DOMAIN"

ln -sf "$DEST" "/etc/nginx/sites-enabled/${DOMAIN}"

nginx -t
systemctl reload nginx
echo "OK  nginx $DOMAIN applied (TLS from $nginx_ssl_dir)"

STATIC="$ROOT/services/ops-web/.next/standalone/.next/static/css"
if [[ -d "$STATIC" ]]; then
  css="$(basename "$(ls "$STATIC"/*.css | head -1)")"
  code="$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}/_next/static/css/${css}")"
  echo "Probe https://${DOMAIN}/_next/static/css/${css} → HTTP $code"
fi
