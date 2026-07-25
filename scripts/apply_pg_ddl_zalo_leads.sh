#!/usr/bin/env bash
# Wave Z2 — zalo lead form poll DDL
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 - <<'PY'
from ptt_crm.pg_schema import pg_v3_ready, apply_ddl_zalo_leads, pg_zalo_leads_ready
assert pg_v3_ready(), 'pg v3 not ready — apply v3 DDL first'
apply_ddl_zalo_leads()
assert pg_zalo_leads_ready(), 'zalo_lead_form_sync_cursor / zalo_lead_events missing'
print('OK: zalo leads DDL applied')
PY
