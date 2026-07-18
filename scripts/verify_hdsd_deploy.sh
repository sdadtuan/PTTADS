#!/usr/bin/env bash
# Kiểm tra deploy HDSD trên VPS — chạy trong thư mục app (vd. /var/www/qlptt)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== HDSD deploy check ==="
echo "PWD: $(pwd)"
echo

echo "1. Route trong app.py:"
grep -c 'crm/hdsd' app.py || true
echo

echo "2. Template sidebar:"
grep -n 'HDSD\|Hướng dẫn' templates/partials/admin_sidebar.html || echo "MISSING sidebar HDSD"
echo

echo "3. Topbar HDSD:"
grep -n 'topbar-link--hdsd\|crm_hdsd_page' templates/partials/admin_topbar.html || echo "MISSING topbar HDSD"
echo

echo "4. JS không ẩn HDSD:"
grep -n 'admin-nav-link--always\|crm_hdsd' static/admin_section_gating.js | head -5 || echo "MISSING js fix"
echo

echo "5. Flask routes:"
./.venv/bin/python -c "from app import app; print([r.rule for r in app.url_map.iter_rules() if 'hdsd' in r.rule])" 2>/dev/null || echo "python import failed"
echo

echo "6. HTTP (port 8007 — đổi nếu khác):"
curl -s -o /dev/null -w "  /crm/hdsd => HTTP %{http_code}\n" http://127.0.0.1:8007/crm/hdsd || true
echo

echo "7. Sidebar HTML qua HTTP (cần cookie admin — chỉ kiểm tra chuỗi trong response login page):"
curl -s http://127.0.0.1:8007/admin/login | grep -o 'HDSD' | head -1 || echo "  (login page không có HDSD — bình thường; kiểm tra sau khi đăng nhập View Source)"
