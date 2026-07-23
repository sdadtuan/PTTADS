#!/usr/bin/env bash
# Wave B3.5 — dry-run Meta Ads Flask retirement pack (M1-G11).
# Run before B3.6 APPLY on VPS:
#   ./scripts/wave_b3_5_deploy.sh
#   sudo -E ./scripts/wave_b3_5_deploy.sh   # same dry-run, optional sudo for systemd probe
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

echo "== Wave B3.5 deploy (Meta retirement dry-run / M1-G11) =="

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  export PTT_ENV_FILE="$ENV_FILE"
fi

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export HORIZON1_SKIP_SOAK="${HORIZON1_SKIP_SOAK:-1}"
export HORIZON1_SKIP_NEST_SMOKE="${HORIZON1_SKIP_NEST_SMOKE:-1}"
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}"
export HORIZON1_SKIP_SYSTEMD="${HORIZON1_SKIP_SYSTEMD:-1}"
export CRM_FACEBOOK_BACKGROUND=1
export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1

echo "-- meta retirement preflight dry-run --"
"$PYTHON" -m ptt_crm.meta_ads_retirement_preflight run

echo ""
echo "-- close_flask_retirement_meta_ads.sh (APPLY=0) --"
chmod +x "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
APPLY=0 "$ROOT/scripts/close_flask_retirement_meta_ads.sh"

echo ""
echo "-- horizon1 gates with M1-G11 --"
export HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN=1
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates

echo ""
echo "-- persist dry-run verified flag (Nest migration-status fallback) --"
if [[ -f "$ENV_FILE" ]]; then
  touch "$ENV_FILE"
  if grep -q '^HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED=' "$ENV_FILE" 2>/dev/null; then
    sed -i.bak 's|^HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED=.*|HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED=1|' "$ENV_FILE"
  else
    echo 'HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED=1' >>"$ENV_FILE"
  fi
fi

echo ""
echo "Wave B3.5 dry-run OK."
echo "Next: sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh  (B3.6)"
echo "Smoke: ./scripts/wave_b3_5_smoke.sh"
