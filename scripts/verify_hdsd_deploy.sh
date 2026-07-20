#!/usr/bin/env bash
# Kiểm tra HDSD docs trên ops-web — Flask HTTP retired
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== HDSD deploy check (ops-web) ==="
echo "PWD: $(pwd)"
echo

HDSd_PAGE="services/ops-web/src/app/crm/hdsd/page.tsx"
if [[ -f "$HDSd_PAGE" ]]; then
  echo "OK  ops-web HDSD page: $HDSd_PAGE"
else
  echo "WARN ops-web HDSD page missing — add /crm/hdsd on ops-web if needed"
fi

if [[ -d docs/crm ]] || [[ -d docs/runbooks ]]; then
  echo "OK  docs/ present for HDSD content"
else
  echo "WARN docs/ not found"
fi

echo
echo "Flask app.py retired — staff UI: https://ops.pttads.vn/crm/hdsd (when deployed)"
