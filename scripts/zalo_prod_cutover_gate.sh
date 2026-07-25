#!/usr/bin/env bash
# Prod-S3 — Zalo production cutover gate (PROD-P0-ZALO / P0-Z-Q1)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ZALO_PROD_ENV:-$ROOT/deploy/env.zalo-prod.example}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export BASE="$PTT_API_URL"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }
warn() { echo "WARN $*"; }

echo "== Prod-S3 Zalo production cutover gate =="
echo "   ENV_FILE=$ENV_FILE"
echo "   PTT_ZALO_ADS_STUB=${PTT_ZALO_ADS_STUB:-?}"
echo "   PTT_ZALO_ADS_PILOT=${PTT_ZALO_ADS_PILOT:-?}"
echo "   PTT_ZALO_TOKEN_REFRESH=${PTT_ZALO_TOKEN_REFRESH:-0}"
echo "   PTT_ZALO_FORM_POLL=${PTT_ZALO_FORM_POLL:-0}"

if [[ "${PTT_ZALO_ADS_STUB:-1}" == "1" ]]; then
  bad "PTT_ZALO_ADS_STUB must be 0 for prod cutover"
else
  ok "stub disabled (PTT_ZALO_ADS_STUB=0)"
fi

if [[ "${PTT_ZALO_INSIGHTS_SYNC:-0}" != "1" ]]; then
  bad "PTT_ZALO_INSIGHTS_SYNC must be 1"
else
  ok "insights sync enabled"
fi

if [[ -z "${PTT_ZALO_APP_ID:-}" || -z "${PTT_ZALO_APP_SECRET:-}" || -z "${PTT_ZALO_OAUTH_REDIRECT_URI:-}" ]]; then
  warn "Zalo OAuth env incomplete — required on VPS prod"
else
  ok "Zalo OAuth env present"
fi

echo ""
echo "==> Wave Z2 gate (DDL + API smoke)"
if bash "$ROOT/scripts/staging_zalo_wave_z2_gate.sh"; then
  ok "Wave Z2 gate"
else
  bad "Wave Z2 gate failed"
fi

echo ""
echo "==> Jest pilot util (production mode)"
if (cd "$ROOT/services/ptt-crm-api" && npx jest src/agency/zalo-ads-pilot.util.spec.ts --silent 2>/dev/null); then
  ok "zalo-ads-pilot.util.spec.ts"
else
  warn "jest zalo-ads-pilot.util.spec.ts skipped or failed"
fi

echo ""
echo "==> Python token refresh + form poll SLA modules"
if python3 -c "
from ptt_zalo.token_refresh import sync_zalo_token_refresh
from ptt_zalo.form_poll_sla import evaluate_form_poll_sla
assert sync_zalo_token_refresh(dry_run=True).get('skipped') or sync_zalo_token_refresh(dry_run=True).get('ok')
assert evaluate_form_poll_sla(dry_run=True).get('ok') or evaluate_form_poll_sla(dry_run=True).get('skipped')
print('OK  python modules import')
"; then
  :
else
  bad "python Prod-S3 modules"
fi

if [[ -n "${STAFF_TOKEN:-}" ]]; then
  pilot_body="$(curl -sf "$BASE/api/v1/zalo-ads/pilot-status" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  stub_flag="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print(d.get('pilot',{}).get('stub_mode',''))" "$pilot_body" 2>/dev/null || echo '')"
  if [[ "$stub_flag" == "False" || "$stub_flag" == "false" ]]; then
    ok "pilot-status stub_mode=false"
  else
    warn "pilot-status stub_mode not false (API may use staging env)"
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Prod-S3 Zalo production cutover gate PASSED"
  exit 0
fi
echo "Prod-S3 Zalo production cutover gate FAILED"
exit 1
