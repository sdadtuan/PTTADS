#!/usr/bin/env bash
# Prod-Z4 — Zalo campaign write (GAP-Z4-01)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Prod-Z4 Zalo campaign write gate =="

for f in \
  ptt_zalo/campaign_write.py \
  docs/specs/2026-07-26-postgresql-ddl-z4-campaign-writes.sql \
  services/ptt-crm-api/src/campaign-writes/zalo-campaign-write-pilot.util.ts \
  services/ptt-crm-api/src/zalo-ads-ops/zalo-ads-ops.module.ts \
  services/ptt-crm-api/src/agency/agency-campaign-write-internal.controller.ts; do
  if [[ -f "$ROOT/$f" ]]; then ok "$f"; else bad "missing $f"; fi
done

if (cd "$ROOT" && python3 -m unittest tests.test_zalo_campaign_write -q 2>/dev/null); then
  ok "test_zalo_campaign_write"
else
  bad "test_zalo_campaign_write failed"
fi

if rg -q "_execute_zalo_write|channel == \"zalo\"" "$ROOT/ptt_temporal/activities/campaign_write.py" 2>/dev/null; then
  ok "worker zalo dispatch"
else
  bad "worker missing zalo dispatch"
fi

if rg -q "auto_hub_map_from_campaign_write" "$ROOT/ptt_crm/nest_api.py" 2>/dev/null; then
  ok "nest auto hub map bridge"
else
  bad "missing nest auto hub map bridge"
fi

if [[ "$fail" -eq 0 ]]; then
  echo "Prod-Z4 gate PASSED"
  exit 0
fi
echo "Prod-Z4 gate FAILED"
exit 1
