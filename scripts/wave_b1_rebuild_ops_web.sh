#!/usr/bin/env bash
# Rebuild ops-web standalone + copy static assets (fixes blank pages / 404 on /_next/static).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"

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

css_file="$(ls .next/standalone/.next/static/css/*.css 2>/dev/null | head -1 || true)"
if [[ -z "$css_file" ]]; then
  echo "FAIL  .next/standalone/.next/static/css missing after copy"
  exit 1
fi
echo "OK  static copied ($(basename "$css_file"))"

if [[ -f "$ROOT/deploy/ptt-ops-web.service" ]]; then
  echo "Note: systemd should use WorkingDirectory=.../ops-web/.next/standalone"
  echo "      Run: sudo cp $ROOT/deploy/ptt-ops-web.service /etc/systemd/system/ && sudo systemctl daemon-reload"
fi

if systemctl restart ptt-ops-web 2>/dev/null; then
  echo "OK  restarted ptt-ops-web"
else
  echo "Run: sudo systemctl restart ptt-ops-web"
fi

sleep 2
css_name="$(basename "$css_file")"
code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3200/_next/static/css/$css_name")"
echo "probe /_next/static/css/$css_name → HTTP $code"
if [[ "$code" != "200" ]]; then
  echo "FAIL  static still 404 — check WorkingDirectory in ptt-ops-web.service"
  exit 1
fi
echo "OK  ops-web static assets served"
