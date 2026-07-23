#!/usr/bin/env bash
# Wave B3.5 smoke — Meta Ads retirement dry-run preflight (M1-G11).
#
# Usage:
#   ./scripts/wave_b3_5_smoke.sh
#   HORIZON1_SKIP_SYSTEMD=0 ./scripts/wave_b3_5_smoke.sh   # VPS systemd probe
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B3.5 smoke (retirement dry-run) =="

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=1
export HORIZON1_SKIP_SYSTEMD="${HORIZON1_SKIP_SYSTEMD:-1}"

"$PYTHON" -m pytest tests/test_meta_ads_retirement_preflight.py -q --tb=no \
  && ok "pytest meta_ads_retirement_preflight" \
  || bad "pytest meta_ads_retirement_preflight"

"$PYTHON" -m ptt_crm.meta_ads_retirement_preflight run >/dev/null \
  && ok "preflight dry-run artifact" \
  || bad "preflight dry-run artifact"

"$PYTHON" -m ptt_crm.meta_ads_retirement_preflight verify >/dev/null \
  && ok "verify dry-run artifact" \
  || bad "verify dry-run artifact"

chmod +x "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
if APPLY=0 "$ROOT/scripts/close_flask_retirement_meta_ads.sh" >/dev/null; then
  ok "close_flask_retirement_meta_ads dry-run"
else
  bad "close_flask_retirement_meta_ads dry-run"
fi

export HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN=1
gate_json="$("$PYTHON" -m ptt_crm.horizon1_meta_ads_gates 2>/dev/null || true)"
if echo "$gate_json" | python3 -c "
import sys, json
r = json.load(sys.stdin)
checks = {c['id']: c for c in r.get('checks', [])}
g11 = checks.get('M1-G11', {})
sys.exit(0 if g11.get('ok') else 1)
"; then
  ok "horizon1 gate M1-G11"
else
  bad "horizon1 gate M1-G11"
fi

art="$PTT_ARTIFACTS_DIR/horizon1-meta-ads-retirement-dry-run.json"
if [[ -f "$art" ]]; then
  python3 -c "
import json
d = json.load(open('$art'))
assert d.get('dry_run') is True, d
assert d.get('ok') is True, d
plan = d.get('apply_plan') or {}
assert plan.get('partial_retire') is True, plan
assert plan.get('stop_ptt_service') is False, plan
print('pending env', d['steps']['env_diff']['pending_changes'])
"
  ok "artifact apply_plan partial_retire"
else
  bad "missing $art"
fi

chmod +x "$ROOT/scripts/verify_meta_ads_retirement_dry_run.sh"
if "$ROOT/scripts/verify_meta_ads_retirement_dry_run.sh" verify >/dev/null; then
  ok "verify_meta_ads_retirement_dry_run.sh"
else
  bad "verify_meta_ads_retirement_dry_run.sh"
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
assert 'gate_m1_g11' in b, b
print('gate_m1_g11', b.get('gate_m1_g11'), 'pending', b.get('retirement_env_pending_changes'))
"
      ok "GET migration-status gate_m1_g11"
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
  echo "Wave B3.5 smoke PASSED"
  exit 0
fi
echo "Wave B3.5 smoke FAILED"
exit 1
