#!/usr/bin/env bash
# Thử sửa ops-web static khi deploy KHÔNG có sudo / quên password linuxuser.
#   cd /var/www/ptt && ./scripts/wave_b1_ops_web_no_sudo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STANDALONE="$ROOT/services/ops-web/.next/standalone"
STATIC_CSS="$STANDALONE/.next/static/css"
PORT="${OPS_PORT:-3200}"

echo "== ops-web no-sudo workaround =="

if [[ ! -d "$STATIC_CSS" ]]; then
  echo "FAIL  chưa build static — chạy trước:"
  echo "  export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b1_rebuild_ops_web.sh"
  exit 1
fi

CSS="$(basename "$(ls "$STATIC_CSS"/*.css | head -1)")"
echo "CSS=$CSS"

probe() {
  curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/_next/static/css/$CSS"
}

code="$(probe)"
echo "probe trước → HTTP $code"

if [[ "$code" == "200" ]]; then
  echo "OK  static đã hoạt động — hard refresh https://rs.pttads.vn/agency"
  exit 0
fi

echo ""
echo "-- Kiểm tra sudo không cần password --"
if sudo -n true 2>/dev/null; then
  echo "OK  deploy có passwordless sudo — chạy:"
  echo "  sudo $ROOT/scripts/wave_b1_fix_static_sudo.sh"
  exit 0
fi
echo "Không có passwordless sudo."

echo ""
echo "-- Process đang chiếm :$PORT --"
ss -tlnp 2>/dev/null | grep ":$PORT " || netstat -tlnp 2>/dev/null | grep ":$PORT " || true

pid="$(ss -tlnp 2>/dev/null | grep ":$PORT " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1 || true)"
if [[ -n "$pid" ]]; then
  owner="$(ps -o user= -p "$pid" 2>/dev/null | tr -d ' ' || echo unknown)"
  echo "PID=$pid owner=$owner"
  if [[ "$owner" == "$(whoami)" ]]; then
    echo "Thử kill process cũ và start lại từ standalone..."
    kill "$pid" 2>/dev/null || true
    sleep 2
    # systemd có thể tự restart — nếu vậy cần sudo stop service
    if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
      echo "WARN  :$PORT vẫn bận (systemd Restart=always?) — CẦN sudo stop ptt-ops-web"
    fi
  else
    echo "WARN  process thuộc user $owner — deploy không kill được"
  fi
fi

if ! ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
  echo "Start node từ $STANDALONE ..."
  cd "$STANDALONE"
  export PORT NODE_ENV=production
  nohup node server.js >> "$ROOT/logs/ops-web-manual.log" 2>&1 &
  sleep 2
fi

code="$(probe)"
echo "probe sau  → HTTP $code"

if [[ "$code" == "200" ]]; then
  echo "OK  static hoạt động trên :$PORT"
  echo "    Mở https://rs.pttads.vn/agency (hard refresh)"
  echo "    Log: $ROOT/logs/ops-web-manual.log"
  exit 0
fi

echo ""
echo "FAIL  deploy không đủ quyền — cần MỘT trong các cách sau:"
echo ""
echo "  A) Reset password linuxuser qua Vultr Console:"
echo "     https://my.vultr.com → Server → Settings → Reset Root Password"
echo "     (hoặc Recovery Console → passwd linuxuser)"
echo ""
echo "  B) SSH bằng root nếu có key/password khác, rồi chạy:"
echo "     sudo /var/www/ptt/scripts/wave_b1_fix_static_sudo.sh"
echo ""
echo "  C) Nhờ admin có quyền sudo chạy lệnh trên."
echo ""
exit 1
