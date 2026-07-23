#!/usr/bin/env bash
# Horizon 1 partial — Retire Flask admin for Meta / Facebook Ads hub (ops-web canonical)
#
# Does NOT stop ptt.service — nginx redirect + env flags + webhook Nest-only.
#
# Usage:
#   sudo -E ./scripts/close_flask_retirement_meta_ads.sh
#   sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

ENV_EXAMPLE="${PTT_HORIZON1_ENV:-$ROOT/deploy/env.horizon1-meta-ads.example}"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

APPLY="${APPLY:-0}"
ENV_FILE="${PTT_ENV_FILE:-/var/www/ptt/.env}"
NGINX_SITE="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"
NGINX_SRC="$ROOT/deploy/nginx-rs-delivery-admin-retired.conf"

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export HORIZON1_SKIP_SOAK="${HORIZON1_SKIP_SOAK:-1}"
export HORIZON1_SKIP_NEST_SMOKE="${HORIZON1_SKIP_NEST_SMOKE:-1}"

echo "==> Meta Ads admin retirement — preflight"
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates || {
  echo "FAIL horizon1 meta gates — see .local-dev/horizon1-meta-ads-gate-report.json" >&2
  exit 1
}

echo ""
echo "==> Plan"
echo "    PTT_FLASK_META_ADS_ADMIN_RETIRED=1"
echo "    PTT_WEBHOOKS_NEST_META=1"
echo "    PTT_WEBHOOKS_FLASK_FALLBACK=0"
echo "    nginx: /crm/facebook-ads → ops.pttads.vn/meta/facebook-ads"
echo "    Flask ptt.service KEEPS RUNNING for other CRM routes"
echo "    ptt-fb-autosync.service continues (decouple app.py separately)"

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. Execute on VPS:"
  echo "  sudo -E APPLY=1 $0"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL APPLY=1 requires root (sudo)" >&2
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

echo ""
echo "==> Update $ENV_FILE"
_set_env PTT_FLASK_META_ADS_ADMIN_RETIRED 1
_set_env PTT_WEBHOOKS_NEST_ENABLED 1
_set_env PTT_WEBHOOKS_NEST_META 1
_set_env PTT_WEBHOOKS_FLASK_FALLBACK 0
_set_env CRM_FACEBOOK_BACKGROUND 1
_set_env CRM_FACEBOOK_BACKGROUND_IN_GUNICORN 0

echo ""
echo "==> Merge nginx redirect block"
if [[ -x "$ROOT/scripts/apply_nginx_meta_ads_retired.sh" ]]; then
  "$ROOT/scripts/apply_nginx_meta_ads_retired.sh"
elif grep -q "location ^~ /crm/facebook-ads" "$NGINX_SITE" 2>/dev/null; then
  echo "    nginx already has /crm/facebook-ads redirect"
else
  echo "    Append Meta redirect from $NGINX_SRC (manual merge if custom nginx)"
  cat "$NGINX_SRC" >>"$NGINX_SITE.bak-horizon1-meta"
  echo "    Wrote reference to ${NGINX_SITE}.bak-horizon1-meta — review and merge into live site"
  nginx -t
  systemctl reload nginx
fi

echo ""
echo "==> Restart services (pick up .env + nginx)"
for unit in ptt-crm-api ptt-ops-web ptt ptt.service; do
  if systemctl restart "$unit" 2>/dev/null; then
    echo "OK  restarted $unit"
  fi
done
systemctl restart ptt-fb-autosync.service 2>/dev/null && echo "OK  restarted ptt-fb-autosync" || true

echo ""
echo "DONE Meta Ads admin retirement applied."
echo "Verify: curl -I https://rs.pttads.vn/crm/facebook-ads"
