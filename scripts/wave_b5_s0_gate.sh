#!/usr/bin/env bash
# Wave B5 S0 — contract promote bridge gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PTT_CRM_SERVICE_DELIVERY_NEST=1
export PTT_CRM_LEADS_FUNNEL_NEST=1
export PTT_PRESALES_ON_LEAD=1

fail=0
for f in \
  services/ptt-crm-api/src/leads-contract/leads-contract.module.ts \
  services/ptt-crm-api/src/leads-contract/contract-promote.util.ts \
  services/ptt-crm-api/src/leads-contract/lifecycle-workflow-steps.data.json \
  services/ops-web/src/components/LeadContractPanel.tsx \
  services/ops-web/src/components/ContractApprovalsPanel.tsx \
  docs/specs/2026-07-23-wave-b5-s0-promote-bridge-design.md; do
  if [[ ! -f "$ROOT/$f" ]]; then
    echo "MISSING $f"
    fail=1
  fi
done

cd "$ROOT/services/ptt-crm-api"
npm test -- --testPathPattern='leads-contract|contract-readiness' --silent 2>/dev/null || fail=1

if [[ "$fail" -eq 0 ]]; then
  echo '{"wave":"b5-s0","ok":true}'
  exit 0
fi
echo '{"wave":"b5-s0","ok":false}'
exit 1
