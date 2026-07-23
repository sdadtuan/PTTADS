#!/usr/bin/env bash
# Wave B3.6 — APPLY prod Meta Ads Flask retirement pack (M1-G12).
#
# Run on VPS after B3.5 dry-run PASS:
#   ./scripts/wave_b3_6_deploy.sh                    # plan only
#   sudo -E APPLY=1 ./scripts/wave_b3_6_deploy.sh    # apply prod
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${PTT_ENV_FILE:-/var/www/ptt/.env}"
if [[ ! -f "$ENV_FILE" && -f "$ROOT/.env" ]]; then
  ENV_FILE="$ROOT/.env"
fi
APPLY="${APPLY:-0}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_ENV_FILE="$ENV_FILE"

echo "== Wave B3.6 deploy (Meta retirement APPLY prod / M1-G12) =="

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export CRM_FACEBOOK_BACKGROUND=1
export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0

echo "-- B3.5 prerequisite --"
"$PYTHON" -m ptt_crm.meta_ads_retirement_apply prerequisite

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN plan (no changes):"
  echo "  sudo -E APPLY=1 $ROOT/scripts/wave_b3_6_deploy.sh"
  echo "  sudo -E APPLY=1 $ROOT/scripts/close_flask_retirement_meta_ads.sh"
  echo ""
  echo "Pre-check: ./scripts/wave_b3_5_smoke.sh"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL APPLY=1 requires sudo" >&2
  exit 1
fi

chmod +x "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
export HORIZON1_SKIP_SYSTEMD=0
APPLY=1 "$ROOT/scripts/close_flask_retirement_meta_ads.sh"

echo ""
echo "-- post-apply gates M1-G12 --"
export HORIZON1_EXPECT_META_RETIREMENT_APPLIED=1
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates

echo ""
echo "Wave B3.6 applied. Run: ./scripts/wave_b3_6_smoke.sh"
