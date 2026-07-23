#!/usr/bin/env bash
# Wave B3.3 — Flask Meta admin retired (PTT_FLASK_META_ADS_ADMIN_RETIRED=1, M1-G09).
# Run on VPS after B3.1/B3.2:
#   sudo -E APPLY=1 ./scripts/wave_b3_3_deploy.sh
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

echo "== Wave B3.3 deploy (Flask Meta admin retired) =="

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

echo "-- Nest build --"
cd "$ROOT/services/ptt-crm-api"
npm ci
npm run build

echo "-- horizon1 meta gates (expect M1-G09) --"
cd "$ROOT"
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN OK. Apply on VPS:"
  echo "  sudo -E APPLY=1 $ROOT/scripts/wave_b3_3_deploy.sh"
  echo "Or full retirement pack:"
  echo "  sudo -E APPLY=1 $ROOT/scripts/close_flask_retirement_meta_ads.sh"
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

echo "-- update $ENV_FILE --"
_set_env PTT_FLASK_META_ADS_ADMIN_RETIRED 1
_set_env HORIZON1_EXPECT_META_HUB_RETIRED 1
_set_env PTT_WEBHOOKS_NEST_ENABLED 1
_set_env PTT_WEBHOOKS_NEST_META 1
_set_env PTT_WEBHOOKS_FLASK_FALLBACK 0

chmod +x "$ROOT/scripts/apply_nginx_meta_ads_retired.sh"
"$ROOT/scripts/apply_nginx_meta_ads_retired.sh"

for unit in ptt-crm-api ptt-ops-web ptt ptt.service; do
  systemctl restart "$unit" 2>/dev/null && echo "OK  restarted $unit" || true
done

echo ""
echo "Wave B3.3 applied. Run: ./scripts/wave_b3_3_smoke.sh"
