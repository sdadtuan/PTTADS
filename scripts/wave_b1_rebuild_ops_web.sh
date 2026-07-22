#!/usr/bin/env bash
# Rebuild ops-web only (deploy user — NO systemctl, no polkit prompt).
# After this, run: sudo ./scripts/wave_b1_fix_static_sudo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
STATIC_DIR="$ROOT/services/ops-web/.next/standalone/.next/static"

cd "$ROOT/services/ops-web"
echo "== Rebuild ops-web (deploy) =="
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
echo "============================================"
echo " BƯỚC TIẾP — bắt buộc sudo (linuxuser)"
echo " KHÔNG chọn identity deploy khi polkit hỏi."
echo "============================================"
echo ""
echo "  sudo $ROOT/scripts/wave_b1_fix_static_sudo.sh"
echo ""
echo "(Nhập password của user linuxuser khi sudo hỏi)"
echo ""
