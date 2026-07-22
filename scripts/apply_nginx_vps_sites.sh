#!/usr/bin/env bash
# Copy all active nginx site templates with VPS TLS (/etc/nginx/ssl/portalpttadsvn.*).
#   sudo ./scripts/apply_nginx_vps_sites.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Usage: sudo $0"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

install_site() {
  local src="$1"
  local name="$2"
  local dest="/etc/nginx/sites-available/${name}"
  cp "$src" "$dest"
  ln -sf "$dest" "/etc/nginx/sites-enabled/${name}"
  echo "  → $dest"
}

echo "== Apply nginx sites (TLS: /etc/nginx/ssl/portalpttadsvn.pem) =="
install_site "$ROOT/deploy/nginx-rs-flask-retired.conf" "rs.pttads.vn"
install_site "$ROOT/deploy/nginx-portal.conf" "portal.pttads.vn"
install_site "$ROOT/deploy/nginx-ops.conf" "ops.pttads.vn"

nginx -t
systemctl reload nginx
echo "OK  nginx reloaded"
