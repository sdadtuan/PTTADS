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
echo "=== Cần sudo (user linuxuser) — deploy KHÔNG restart được service ==="
echo "Chạy MỘT lệnh sau (nhập password linuxuser):"
echo "  sudo $ROOT/scripts/wave_b1_fix_static_sudo.sh"
echo ""
echo "Hoặc từng bước:"
echo "  sudo cp $ROOT/deploy/ptt-ops-web.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl restart ptt-ops-web"
echo "  sudo $ROOT/scripts/apply_nginx_rs_static.sh"
echo ""

restarted=0
if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart ptt-ops-web && restarted=1
elif sudo -n systemctl restart ptt-ops-web 2>/dev/null; then
  restarted=1
fi
if [[ "$restarted" -eq 1 ]]; then
  echo "OK  ptt-ops-web restarted"
else
  echo "SKIP restart (no sudo) — chạy wave_b1_fix_static_sudo.sh ở trên"
fi

sleep 2
wd="$(systemctl show ptt-ops-web -p WorkingDirectory --value 2>/dev/null || echo unknown)"
echo "WorkingDirectory=$wd"

node_code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3200/_next/static/css/$css_name")"
echo "probe node  :3200/_next/static/css/$css_name → HTTP $node_code"

public_code="$(curl -sk -o /dev/null -w "%{http_code}" "https://rs.pttads.vn/_next/static/css/$css_name" 2>/dev/null || echo 000)"
echo "probe public rs.pttads.vn → HTTP $public_code"

if [[ "$public_code" == "200" ]]; then
  echo "OK  static served via https://rs.pttads.vn (nginx)"
  exit 0
fi
if [[ "$node_code" == "200" ]]; then
  echo "OK  static served via node :3200"
  exit 0
fi

echo "FAIL  static 404 — bắt buộc chạy: sudo $ROOT/scripts/wave_b1_fix_static_sudo.sh"
exit 1
