#!/usr/bin/env bash
# Phase 5 partial — Retire Flask admin for SEO + Email (ops-web canonical)
#
# Does NOT stop ptt.service — only nginx redirects + env flags.
#
# Usage:
#   sudo -E ./scripts/close_flask_retirement_delivery_admin.sh
#   sudo -E APPLY=1 ./scripts/close_flask_retirement_delivery_admin.sh
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

ENV_EXAMPLE="${PTT_HORIZON0_ENV:-$ROOT/deploy/env.horizon0-gate-a.example}"
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

export PTT_FLASK_SEO_ADMIN_RETIRED="${PTT_FLASK_SEO_ADMIN_RETIRED:-1}"
export PTT_FLASK_EMAIL_ADMIN_RETIRED="${PTT_FLASK_EMAIL_ADMIN_RETIRED:-1}"
export PHASE5DA_EXPECT_SEO_RETIRED="${PHASE5DA_EXPECT_SEO_RETIRED:-1}"
export PHASE5DA_EXPECT_EMAIL_RETIRED="${PHASE5DA_EXPECT_EMAIL_RETIRED:-1}"
export PHASE5DA_SKIP_BUILD="${PHASE5DA_SKIP_BUILD:-1}"

echo "==> Delivery admin retirement — preflight"
"$PYTHON" -m ptt_crm.phase5_delivery_admin_retirement_gates || {
  echo "FAIL delivery admin gates — see .local-dev/phase5-delivery-admin-retirement-gate-report.json" >&2
  exit 1
}

echo ""
echo "==> Plan"
echo "    PTT_FLASK_SEO_ADMIN_RETIRED=1"
echo "    PTT_FLASK_EMAIL_ADMIN_RETIRED=1"
echo "    nginx: /crm/seo → ops.pttads.vn/seo/hub"
echo "    nginx: /crm/email → ops.pttads.vn/email/hub"
echo "    Flask ptt.service KEEPS RUNNING for other CRM routes"

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
_set_env PTT_FLASK_SEO_ADMIN_RETIRED 1
_set_env PTT_FLASK_EMAIL_ADMIN_RETIRED 1
_set_env PTT_SEO_GOVERNANCE_ENABLED "${PTT_SEO_GOVERNANCE_ENABLED:-1}"
_set_env PTT_EMAIL_ENABLED "${PTT_EMAIL_ENABLED:-1}"

echo "==> Nginx rs.pttads.vn — delivery admin redirects"
if [[ -f "$NGINX_SITE" && ! -f "${NGINX_SITE}.pre-delivery-admin.bak" ]]; then
  cp -a "$NGINX_SITE" "${NGINX_SITE}.pre-delivery-admin.bak"
fi
cp -f "$NGINX_SRC" "$NGINX_SITE"
nginx -t
systemctl reload nginx
echo "OK  nginx reloaded"

for unit in ptt-crm-api ptt-ops-web; do
  if systemctl list-unit-files "$unit.service" &>/dev/null; then
    systemctl restart "$unit" 2>/dev/null && echo "OK  restarted $unit" || echo "WARN  $unit restart failed"
  fi
done

echo ""
echo "OK  Delivery admin Flask retirement applied (partial Phase 5)"
echo "    Full Flask stop: ./scripts/close_flask_retirement.sh"
