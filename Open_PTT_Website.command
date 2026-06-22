#!/bin/bash
# Double-click trên macOS: mở Terminal và chạy Flask PTT (giữ cửa sổ mở để web hoạt động).
cd "$(dirname "$0")"
exec bash ./restart_flask.sh
