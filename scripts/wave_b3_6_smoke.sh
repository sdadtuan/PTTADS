#!/usr/bin/env bash
# Wave B3.6 smoke — post-apply Meta Ads retirement (M1-G12 + M1-G06 + M1-G09).
#
# Usage:
#   ./scripts/wave_b3_6_smoke.sh
#   ADMIN_PASSWORD='...' ./scripts/wave_b3_6_smoke.sh
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

echo "== Wave B3.6 smoke (retirement applied) RS=$RS =="

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export HORIZON1_META_RETIREMENT_APPLIED="${HORIZON1_META_RETIREMENT_APPLIED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}"
export PTT_RS_BASE_URL="$RS"
export PTT_OPS_WEB_URL="$OPS"
export CRM_FACEBOOK_BACKGROUND=1
export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0

"$PYTHON" -m pytest tests/test_meta_ads_retirement_apply.py -q --tb=no \
  && ok "pytest meta_ads_retirement_apply" \
  || bad "pytest meta_ads_retirement_apply"

art="$PTT_ARTIFACTS_DIR/horizon1-meta-ads-retirement-applied.json"
if [[ -f "$art" ]]; then
  ok "apply artifact present"
else
  echo "SKIP post-apply verify (VPS: sudo -E APPLY=1 ./scripts/wave_b3_6_deploy.sh)"
fi

if [[ -f "$art" ]]; then
chmod +x "$ROOT/scripts/verify_meta_ads_retirement_applied.sh"
if "$ROOT/scripts/verify_meta_ads_retirement_applied.sh" verify; then
  ok "verify_meta_ads_retirement_applied"
else
  bad "verify_meta_ads_retirement_applied"
fi

export HORIZON1_EXPECT_META_RETIREMENT_APPLIED=1
gate_json="$("$PYTHON" -m ptt_crm.horizon1_meta_ads_gates 2>/dev/null || true)"
if echo "$gate_json" | python3 -c "
import sys, json
r = json.load(sys.stdin)
checks = {c['id']: c for c in r.get('checks', [])}
for gid in ('M1-G09', 'M1-G12'):
    if not checks.get(gid, {}).get('ok'):
        sys.exit(1)
sys.exit(0)
"; then
  ok "horizon1 gates M1-G09 M1-G12"
else
  bad "horizon1 gates M1-G09/M1-G12"
fi

if [[ "${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}" == "0" ]]; then
  chmod +x "$ROOT/scripts/wave_b3_4_smoke.sh"
  if "$ROOT/scripts/wave_b3_4_smoke.sh" >/dev/null 2>&1; then
    ok "wave_b3_4_smoke regression"
  else
    bad "wave_b3_4_smoke regression"
  fi
else
  echo "SKIP wave_b3_4 live redirect (HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=1)"
fi
fi

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
assert b.get('flask_meta_ads_admin_retired') is True, b
assert 'gate_m1_g12' in b, b
print('gate_m1_g12', b.get('gate_m1_g12'), 'applied', b.get('retirement_applied_ok'))
"
      ok "GET migration-status gate_m1_g12"
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
  echo "Wave B3.6 smoke PASSED"
  exit 0
fi
echo "Wave B3.6 smoke FAILED"
exit 1
