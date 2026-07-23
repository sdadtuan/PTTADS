#!/usr/bin/env bash
# Wave B3.4 — nginx redirect verify production (M1-G06).
# Run on VPS after B3.3:
#   ./scripts/wave_b3_4_deploy.sh
#   sudo -E APPLY=1 ./scripts/wave_b3_4_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"
APPLY="${APPLY:-0}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

echo "== Wave B3.4 deploy (nginx redirect verify / M1-G06) =="

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
export HORIZON1_SKIP_SOAK="${HORIZON1_SKIP_SOAK:-1}"
export HORIZON1_SKIP_NEST_SMOKE="${HORIZON1_SKIP_NEST_SMOKE:-1}"
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-0}"
export PTT_RS_BASE_URL="${PTT_RS_BASE_URL:-https://rs.pttads.vn}"
export PTT_OPS_WEB_URL="${PTT_OPS_WEB_URL:-https://ops.pttads.vn}"

echo "-- config + live nginx redirect checks --"
chmod +x "$ROOT/scripts/verify_meta_ads_nginx_redirect.sh"
"$ROOT/scripts/verify_meta_ads_nginx_redirect.sh"

echo "-- horizon1 meta gates (expect M1-G06) --"
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN OK. Apply nginx on VPS if redirect not live yet:"
  echo "  sudo ./scripts/apply_nginx_meta_ads_retired.sh"
  echo "  sudo -E APPLY=1 $ROOT/scripts/wave_b3_4_deploy.sh"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL APPLY=1 requires sudo" >&2
  exit 1
fi

_set_env() {
  local key="$1" val="$2"
  touch "$ENV_FILE"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >>"$ENV_FILE"
  fi
}

chmod +x "$ROOT/scripts/apply_nginx_meta_ads_retired.sh"
"$ROOT/scripts/apply_nginx_meta_ads_retired.sh"

export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
"$ROOT/scripts/verify_meta_ads_nginx_redirect.sh"
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates

echo "-- persist redirect verified flag --"
_set_env HORIZON1_SKIP_NGINX_REDIRECT_VERIFY 0
_set_env HORIZON1_META_NGINX_REDIRECT_VERIFIED 1

echo ""
echo "Wave B3.4 applied. Run: ./scripts/wave_b3_4_smoke.sh"
