#!/usr/bin/env bash
# Wave B3.4 smoke — production nginx redirect /crm/facebook-ads → ops-web (M1-G06).
#
# Usage:
#   ./scripts/wave_b3_4_smoke.sh
#   ADMIN_PASSWORD='...' ./scripts/wave_b3_4_smoke.sh
#   PTT_RS_BASE_URL=https://rs.pttads.vn ./scripts/wave_b3_4_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
RS="${PTT_RS_BASE_URL:-https://rs.pttads.vn}"
OPS="${PTT_OPS_WEB_URL:-https://ops.pttads.vn}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B3.4 smoke RS=$RS OPS=$OPS =="

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
export PTT_RS_BASE_URL="$RS"
export PTT_OPS_WEB_URL="$OPS"

"$PYTHON" -m pytest tests/test_meta_ads_nginx_redirect.py -q --tb=no \
  && ok "pytest meta_ads_nginx_redirect" \
  || bad "pytest meta_ads_nginx_redirect"

chmod +x "$ROOT/scripts/verify_meta_ads_nginx_redirect.sh"
if "$ROOT/scripts/verify_meta_ads_nginx_redirect.sh"; then
  ok "verify_meta_ads_nginx_redirect"
else
  bad "verify_meta_ads_nginx_redirect"
fi

gate_json="$("$PYTHON" -m ptt_crm.horizon1_meta_ads_gates 2>/dev/null || true)"
if echo "$gate_json" | python3 -c "
import sys, json
r = json.load(sys.stdin)
checks = {c['id']: c for c in r.get('checks', [])}
g06 = checks.get('M1-G06', {})
sys.exit(0 if g06.get('ok') else 1)
"; then
  ok "horizon1 gate M1-G06"
else
  bad "horizon1 gate M1-G06"
fi

for path in /crm/facebook-ads /crm/facebook-ads/ "/crm/facebook-ads?ref=bookmark"; do
  hdr="$(mktemp)"
  code="$(curl -sfI "${RS}${path}" -o "$hdr" -w '%{http_code}' 2>/dev/null || echo "000")"
  loc="$(grep -i '^location:' "$hdr" 2>/dev/null | tr -d '\r' | cut -d' ' -f2- || true)"
  rm -f "$hdr"
  if [[ "$code" =~ ^30[1278]$ ]] && [[ "$loc" == *"${OPS}/meta/facebook-ads"* ]]; then
    ok "curl ${path} → $code"
  else
    bad "curl ${path} → HTTP $code loc=${loc:-<none>}"
  fi
done

for path in /crm/leads /crm/hub; do
  hdr="$(mktemp)"
  code="$(curl -sfI "${RS}${path}" -o "$hdr" -w '%{http_code}' 2>/dev/null || echo "000")"
  loc="$(grep -i '^location:' "$hdr" 2>/dev/null | tr -d '\r' | cut -d' ' -f2- || true)"
  rm -f "$hdr"
  if [[ "$code" =~ ^30[1278]$ ]] && [[ "$loc" == *"ops.pttads.vn"* ]]; then
    ok "regression ${path} → ops redirect"
  else
    bad "regression ${path} → HTTP $code loc=${loc:-<none>}"
  fi
done

if [[ -n "$PASS" ]]; then
  TOKEN="$(
    curl -sf "$BASE/api/v1/staff/auth/login" \
      -H 'Content-Type: application/json' \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
  )"
  if [[ -n "$TOKEN" ]]; then
    mig_resp="$(mktemp)"
    mig_code="$(curl -s -o "$mig_resp" -w "%{http_code}" \
      "$BASE/api/v1/facebook-ads/migration-status" -H "Authorization: Bearer $TOKEN")"
    if [[ "$mig_code" == "200" ]]; then
      python3 -c "
import json
b = json.load(open('$mig_resp'))
assert b.get('gate_m1_g06') is True, b
print('gate_m1_g06', b.get('gate_m1_g06'), 'config', b.get('gate_m1_g06_config'))
"
      ok "GET migration-status gate_m1_g06"
    else
      bad "GET migration-status HTTP $mig_code"
    fi
    rm -f "$mig_resp"
  else
    bad "staff login"
  fi
else
  echo "SKIP migration-status API (set ADMIN_PASSWORD)"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B3.4 smoke PASSED"
  exit 0
fi
echo "Wave B3.4 smoke FAILED"
exit 1
