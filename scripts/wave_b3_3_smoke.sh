#!/usr/bin/env bash
# Wave B3.3 smoke — PTT_FLASK_META_ADS_ADMIN_RETIRED + migration-status + M1-G09.
# Usage:
#   ADMIN_PASSWORD='...' ./scripts/wave_b3_3_smoke.sh
#   BASE=http://127.0.0.1:3000 PTT_FLASK_META_ADS_ADMIN_RETIRED=1 ./scripts/wave_b3_3_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B3.3 smoke BASE=$BASE =="

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m pytest tests/test_meta_ads_admin_retirement.py -q --tb=no \
  && ok "pytest meta_ads_admin_retirement" \
  || bad "pytest meta_ads_admin_retirement"

gate_json="$("$PYTHON" -m ptt_crm.horizon1_meta_ads_gates 2>/dev/null || true)"
if echo "$gate_json" | python3 -c "
import sys, json
r = json.load(sys.stdin)
checks = {c['id']: c for c in r.get('checks', [])}
g09 = checks.get('M1-G09', {})
sys.exit(0 if g09.get('ok') else 1)
"; then
  ok "horizon1 gate M1-G09"
else
  bad "horizon1 gate M1-G09"
fi

if [[ -n "$PASS" ]]; then
  TOKEN="$(
    curl -sf "$BASE/api/v1/staff/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
  )"
  if [[ -n "$TOKEN" ]]; then
    ok "staff login"
    mig_resp="$(mktemp)"
    mig_code="$(curl -s -o "$mig_resp" -w "%{http_code}" \
      "$BASE/api/v1/facebook-ads/migration-status" -H "Authorization: Bearer $TOKEN")"
    if [[ "$mig_code" == "200" ]]; then
      python3 -c "
import json
b = json.load(open('$mig_resp'))
assert b.get('flask_meta_ads_admin_retired') is True, b
assert b.get('gate_m1_g09') is True, b
print('canonical', b.get('canonical_upstream'))
"
      ok "GET migration-status retired=true"
    else
      bad "GET migration-status HTTP $mig_code"
    fi
    rm -f "$mig_resp"
  else
    bad "staff login"
  fi
else
  echo "SKIP staff migration-status (set ADMIN_PASSWORD)"
fi

nginx_site="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"
if [[ -f "$nginx_site" ]] && grep -q 'location \^~ /crm/facebook-ads' "$nginx_site"; then
  ok "nginx /crm/facebook-ads redirect configured"
else
  echo "WARN nginx redirect not verified (run sudo ./scripts/apply_nginx_meta_ads_retired.sh on VPS)"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B3.3 smoke PASSED"
  exit 0
fi
echo "Wave B3.3 smoke FAILED"
exit 1
