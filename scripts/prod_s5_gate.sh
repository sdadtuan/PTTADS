#!/usr/bin/env bash
# Prod-S5 — onboard wizard + finance strict gate
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Prod-S5 onboard wizard + finance strict gate =="

if [[ -f "$ROOT/services/ops-web/src/components/ClientOnboardWizard.tsx" ]]; then
  ok "ClientOnboardWizard component"
else
  bad "missing ClientOnboardWizard"
fi

if [[ -f "$ROOT/services/ptt-crm-api/src/service-lifecycle/lifecycle-onboard-gate.util.ts" ]]; then
  ok "lifecycle onboard deliver gate util"
else
  bad "missing lifecycle-onboard-gate.util"
fi

if [[ -f "$ROOT/services/ptt-crm-api/src/service-lifecycle/lifecycle-finance-confirm.repository.ts" ]]; then
  ok "lifecycle_finance_confirm audit repo"
else
  bad "missing lifecycle-finance-confirm.repository"
fi

if (cd "$ROOT/services/ptt-crm-api" && npx jest \
  src/service-lifecycle/lifecycle-onboard-gate.util.spec.ts \
  src/service-lifecycle/lifecycle-payment-gate.util.spec.ts \
  src/service-lifecycle/lifecycle-stage.util.spec.ts \
  --silent 2>/dev/null); then
  ok "Prod-S5 unit tests"
else
  bad "Prod-S5 unit tests failed"
fi

if [[ "$fail" -eq 0 ]]; then
  echo "Prod-S5 gate PASSED"
  exit 0
fi
echo "Prod-S5 gate FAILED"
exit 1
