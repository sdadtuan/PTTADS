#!/usr/bin/env bash
# Dừng Flask PTT đang nghe cổng PORT (mặc định 5050), rồi chạy lại.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-5050}"
export PORT

if [[ ! -x "./.venv/bin/python" ]]; then
  echo "Chưa có .venv trong $(pwd)" >&2
  echo "Chạy: python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if PIDS=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null); then
  echo "Đang dừng tiến trình trên cổng ${PORT}: ${PIDS}"
  kill ${PIDS} 2>/dev/null || true
  sleep 1
fi

echo ""
echo "  === Giữ cửa sổ Terminal MỞ — đóng Terminal là tắt web ==="
echo "  === Chỉ dùng http:// (KHÔNG dùng https://) ==="
echo ""
echo "  → PTT site (sau khi thấy 'Running on'): http://127.0.0.1:${PORT}/"
if LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null); then
  echo "  → Cùng Wi‑Fi (điện thoại/máy khác): http://${LAN_IP}:${PORT}/"
fi
echo "  → Kiểm tra: curl -s http://127.0.0.1:${PORT}/healthz"
echo ""

# macOS: mở trình duyệt sau khi server bind xong
if [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
  (sleep 2 && open "http://127.0.0.1:${PORT}/") &
fi

exec ./.venv/bin/python app.py
