#!/usr/bin/env bash
# Phase 5 — Retire Flask monolith (stop/disable ptt.service)
#
# Prerequisites:
#   - Phase 2/3/4 prod cutover complete
#   - ./scripts/staging_phase5_gate_pack.sh PASS
#   - Phase 4 readonly soak ≥14 days (see phase4-prod-cutover-checklist.md)
#
# Usage:
#   set -a && source deploy/env.phase5-flask-retire.example && set +a
#   sudo -E ./scripts/close_flask_retirement.sh              # dry-run
#   sudo -E APPLY=1 ./scripts/close_flask_retirement.sh      # execute
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

ENV_EXAMPLE="${PTT_PHASE5_ENV:-$ROOT/deploy/env.phase5-flask-retire.example}"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

APPLY="${APPLY:-0}"
ENV_FILE="${PTT_ENV_FILE:-/var/www/ptt/.env}"
NGINX_SITE="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"
NGINX_RETIRED_SRC="$ROOT/deploy/nginx-rs-flask-retired.conf"
FLASK_UNIT="${PTT_SYSTEMD_UNIT:-ptt.service}"

echo "==> Phase 5 Flask retirement — preflight"
: "${DATABASE_URL:?Set DATABASE_URL}"

export PTT_FLASK_MONOLITH_MODE="${PTT_FLASK_MONOLITH_MODE:-retired}"
export PHASE5_EXPECT_FLASK_MODE="${PHASE5_EXPECT_FLASK_MODE:-retired}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export PHASE5_SKIP_PRIOR_GATES="${PHASE5_SKIP_PRIOR_GATES:-0}"

"$PYTHON" -m ptt_crm.phase5_flask_retirement_gates || {
  echo "FAIL retirement gates — see .local-dev/phase5-flask-retirement-gate-report.json" >&2
  exit 1
}

echo ""
echo "==> Retirement plan"
echo "    PTT_FLASK_MONOLITH_MODE=$PTT_FLASK_MONOLITH_MODE"
echo "    PTT_WEBHOOKS_FLASK_FALLBACK=$PTT_WEBHOOKS_FLASK_FALLBACK"
echo "    Stop/disable: $FLASK_UNIT"
echo "    Keep running: ptt-crm-api ptt-worker ptt-fb-autosync ptt-temporal-worker ops-web portal-web"
echo "    Nginx rs.pttads.vn → $NGINX_RETIRED_SRC"

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. To execute on VPS:"
  echo "  sudo -E APPLY=1 $0"
  echo ""
  echo "Rollback (emergency):"
  echo "  sudo systemctl enable --now $FLASK_UNIT"
  echo "  Set PTT_FLASK_MONOLITH_MODE=readonly in $ENV_FILE"
  echo "  Restore nginx from backup: ${NGINX_SITE}.pre-phase5.bak"
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
_set_env PTT_FLASK_MONOLITH_MODE retired
_set_env PTT_WEBHOOKS_FLASK_FALLBACK 0
_set_env PTT_WEBHOOKS_NEST_ENABLED 1
_set_env PTT_WEBHOOKS_NEST_META 1
_set_env PTT_LEADS_WRITE_SOURCE pg
_set_env PTT_LEAD_INGEST_RULES_SOURCE pg
_set_env PTT_PORTAL_SEO_ENABLED "${PTT_PORTAL_SEO_ENABLED:-1}"
_set_env PTT_SEO_GOVERNANCE_ENABLED "${PTT_SEO_GOVERNANCE_ENABLED:-1}"

echo "==> Nginx rs.pttads.vn — redirect legacy admin to ops-web"
if [[ -f "$NGINX_SITE" && ! -f "${NGINX_SITE}.pre-phase5.bak" ]]; then
  cp -a "$NGINX_SITE" "${NGINX_SITE}.pre-phase5.bak"
fi
cp -f "$NGINX_RETIRED_SRC" "$NGINX_SITE"
nginx -t
systemctl reload nginx
echo "OK  nginx reloaded (Flask upstream removed)"

echo ""
echo "==> Stop Flask Gunicorn ($FLASK_UNIT)"
systemctl stop "$FLASK_UNIT" 2>/dev/null || true
systemctl disable "$FLASK_UNIT" 2>/dev/null || true
echo "OK  $FLASK_UNIT stopped and disabled"

echo ""
echo "==> Restart Nest / workers / Next.js (no Flask dependency)"
for unit in ptt-crm-api ptt-worker ptt-fb-autosync ptt-temporal-worker ptt-ops-web ptt-portal-web; do
  if systemctl list-unit-files "$unit.service" &>/dev/null; then
    systemctl restart "$unit" 2>/dev/null && echo "OK  restarted $unit" || echo "WARN  $unit restart failed"
  fi
done

echo ""
echo "==> Health smoke"
curl -sf http://127.0.0.1:3000/health >/dev/null && echo "OK  Nest /health" || echo "WARN  Nest health failed"
curl -sf -o /dev/null -w "rs.pttads.vn HTTP %{http_code}\n" https://rs.pttads.vn/ 2>/dev/null || echo "WARN  rs.pttads.vn check skipped"

echo ""
echo "==> Soak record (day 0 — Flask retired)"
"$ROOT/scripts/phase5_soak_record.sh" || true

echo ""
echo "OK  Phase 5 Flask retirement applied"
echo "    Gate report: $PTT_ARTIFACTS_DIR/phase5-flask-retirement-gate-report.json"
echo "    Runbook: docs/runbooks/phase5-flask-retirement-checklist.md"
echo "    Daily soak ≥14d: ./scripts/phase5_soak_record.sh"
