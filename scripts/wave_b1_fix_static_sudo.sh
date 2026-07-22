#!/usr/bin/env bash
# Run ONCE with sudo (linuxuser/root) — fixes blank ops-web pages.
#   cd /var/www/ptt && sudo ./scripts/wave_b1_fix_static_sudo.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Usage: sudo $0"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC_CSS="$ROOT/services/ops-web/.next/standalone/.next/static/css"

echo "== Wave B1 static fix (sudo) =="

if [[ ! -d "$STATIC_CSS" ]]; then
  echo "FAIL  static missing — run as deploy first:"
  echo "  cd $ROOT && export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b1_rebuild_ops_web.sh"
  exit 1
fi

CSS="$(basename "$(ls "$STATIC_CSS"/*.css | head -1)")"
echo "CSS=$CSS"

echo "-- ptt-ops-web.service --"
cp "$ROOT/deploy/ptt-ops-web.service" /etc/systemd/system/ptt-ops-web.service
systemctl daemon-reload
systemctl restart ptt-ops-web
sleep 2
systemctl is-active ptt-ops-web
echo "WorkingDirectory=$(systemctl show ptt-ops-web -p WorkingDirectory --value)"
echo "ExecStart=$(systemctl show ptt-ops-web -p ExecStart --value)"

node_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3200/_next/static/css/$CSS")"
echo "node :3200/_next/static/css/$CSS → HTTP $node_code"

echo "-- nginx rs.pttads.vn (TLS /etc/nginx/ssl + static alias) --"
"$ROOT/scripts/apply_nginx_rs_vps_ssl.sh"

pub_code="$(curl -sk -o /dev/null -w "%{http_code}" "https://rs.pttads.vn/_next/static/css/$CSS")"
echo "https rs.pttads.vn/_next/static/css/$CSS → HTTP $pub_code"

if [[ "$pub_code" != "200" && "$node_code" != "200" ]]; then
  echo "FAIL  static still not served"
  ls -la "$STATIC_CSS/$CSS" || true
  journalctl -u ptt-ops-web -n 20 --no-pager || true
  exit 1
fi

echo ""
echo "OK  Static assets fixed. Hard-refresh browser: https://rs.pttads.vn/agency"
