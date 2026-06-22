#!/usr/bin/env bash
# Chạy PTT app bằng Python trong .venv (tránh lỗi: No module named 'flask').
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Chưa có .venv. Tạo và cài package:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
exec .venv/bin/python app.py "$@"
