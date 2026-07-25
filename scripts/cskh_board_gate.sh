#!/usr/bin/env bash
# Prod-S4 — CSKH board gate (P0-C-Q1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Prod-S4 CSKH board gate =="

if [[ -f "$ROOT/services/ops-web/src/app/crm/cskh-board/page.tsx" ]]; then
  ok "ops-web /crm/cskh-board page"
else
  bad "missing cskh-board page"
fi

if [[ -f "$ROOT/services/ptt-crm-api/src/cskh-board/cskh-board.controller.ts" ]]; then
  ok "Nest cskh-board controller"
else
  bad "missing cskh-board controller"
fi

if (cd "$ROOT/services/ptt-crm-api" && npx jest src/cskh-board/cskh-board-sla.util.spec.ts --silent 2>/dev/null); then
  ok "cskh-board-sla.util.spec.ts"
else
  bad "SLA unit tests failed"
fi

if python3 -c "from ptt_crm.prod_h_gates import audit_prod_stub_flags; print(audit_prod_stub_flags())"; then
  ok "prod_h_gates import"
else
  bad "prod_h_gates import"
fi

if [[ "$fail" -eq 0 ]]; then
  echo "Prod-S4 CSKH board gate PASSED"
  exit 0
fi
echo "Prod-S4 CSKH board gate FAILED"
exit 1
