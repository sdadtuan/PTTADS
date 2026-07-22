#!/usr/bin/env bash
# Rebuild ops-web standalone + copy static assets (fixes blank pages / 404 on /_next/static).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
STATIC_DIR="$ROOT/services/ops-web/.next/standalone/.next/static"

cd "$ROOT/services/ops-web"
echo "== Rebuild ops-web =="
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"
git -C "$ROOT" log -1 --oneline

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

css_file="$(ls "$STATIC_DIR"/css/*.css 2>/dev/null | head -1 || true)"
if [[ -z "$css_file" ]]; then
  echo "FAIL  $STATIC_DIR/css missing after copy"
  exit 1
fi
css_name="$(basename "$css_file")"
echo "OK  static copied ($css_name)"
ls -la "$css_file"

echo ""
echo "-- systemd (requires sudo once) --"
echo "sudo cp $ROOT/deploy/ptt-ops-web.service /etc/systemd/system/"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl restart ptt-ops-web"
echo ""
echo "-- nginx static alias (requires sudo once) --"
echo "sudo $ROOT/scripts/apply_nginx_rs_static.sh"
echo ""

restarted=0
if systemctl is-active ptt-ops-web >/dev/null 2>&1; then
  if systemctl restart ptt-ops-web 2>/dev/null; then
    restarted=1
    echo "OK  systemctl restart ptt-ops-web (user session)"
  fi
fi
if [[ "$restarted" -eq 0 ]]; then
  echo "WARN  could not restart ptt-ops-web — run: sudo systemctl restart ptt-ops-web"
fi

sleep 2
wd="$(systemctl show ptt-ops-web -p WorkingDirectory --value 2>/dev/null || echo unknown)"
echo "WorkingDirectory=$wd"

node_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3200/_next/static/css/$css_name")"
echo "probe node  :3200/_next/static/css/$css_name → HTTP $node_code"

public_code="$(curl -sk -o /dev/null -w "%{http_code}" "https://rs.pttads.vn/_next/static/css/$css_name" 2>/dev/null || echo 000)"
echo "probe public rs.pttads.vn → HTTP $public_code"

if [[ "$public_code" == "200" ]]; then
  echo "OK  static served via nginx/https"
  exit 0
fi
if [[ "$node_code" == "200" ]]; then
  echo "OK  static served via node :3200 (apply nginx alias for production)"
  exit 0
fi

echo "FAIL  static still 404"
echo "  1) sudo cp $ROOT/deploy/ptt-ops-web.service /etc/systemd/system/ && sudo systemctl daemon-reload"
echo "  2) sudo systemctl restart ptt-ops-web"
echo "  3) sudo $ROOT/scripts/apply_nginx_rs_static.sh"
exit 1
