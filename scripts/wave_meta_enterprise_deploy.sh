#!/usr/bin/env bash
# Meta Enterprise — VPS deploy: pull + DDL v4/v5 + build + restart + smoke
#
# One-liner (on VPS as deploy user):
#   cd /var/www/ptt && ./scripts/wave_meta_enterprise_deploy.sh
#
# Dry-run preflight (no pull/build/restart):
#   cd /var/www/ptt && META_DEPLOY_APPLY=0 ./scripts/wave_meta_enterprise_deploy.sh
#
# Env:
#   META_DEPLOY_APPLY=1     0 = preflight only (default: 1)
#   GIT_PULL=1              git pull --ff-only before deploy (default: 1)
#   META_APPLY_DDL=1        apply PG DDL v4 + v5 (default: 1)
#   META_SKIP_BUILD=0       skip npm builds (default: 0)
#   META_SKIP_PORTAL=0      skip portal-web build (default: 0)
#   META_SKIP_SMOKE=0       skip post-deploy smoke (default: 0)
#   META_UPDATE_ENV=0       merge safe Meta flags into .env if missing (default: 0)
#   NEXT_PUBLIC_PTT_API_URL public API URL for ops-web build (default: from .env or https://rs.pttads.vn)
#   PTT_ENV_FILE            path to .env (default: $ROOT/.env)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"
META_DEPLOY_APPLY="${META_DEPLOY_APPLY:-1}"
GIT_PULL="${GIT_PULL:-1}"
META_APPLY_DDL="${META_APPLY_DDL:-1}"
META_SKIP_BUILD="${META_SKIP_BUILD:-0}"
META_SKIP_PORTAL="${META_SKIP_PORTAL:-0}"
META_SKIP_SMOKE="${META_SKIP_SMOKE:-0}"
META_UPDATE_ENV="${META_UPDATE_ENV:-0}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

OPS_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://rs.pttads.vn}"
export NEXT_PUBLIC_PTT_API_URL="$OPS_API_URL"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

merge_env_line() {
  local key="$1"
  local val="$2"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "WARN  $ENV_FILE missing — set $key=$val manually"
    return 0
  fi
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  echo "${key}=${val}" >>"$ENV_FILE"
  echo "ADD  ${key}=${val}"
}

echo "== Meta Enterprise deploy =="
echo "ROOT=$ROOT"
echo "META_DEPLOY_APPLY=$META_DEPLOY_APPLY"
echo "NEXT_PUBLIC_PTT_API_URL=$OPS_API_URL"
echo "META_APPLY_DDL=$META_APPLY_DDL"

echo "-- preflight --"
test -d "$ROOT/.git" || { echo "FAIL: not a git repo: $ROOT"; exit 1; }
for f in \
  scripts/apply_pg_ddl_v4_meta_enterprise.sh \
  scripts/apply_pg_ddl_v5_meta_conversion.sh \
  scripts/wave_meta_enterprise_smoke.sh \
  scripts/wave_meta_phase0_gate.sh; do
  test -f "$ROOT/$f" || { echo "FAIL: missing $f — git pull origin main"; exit 1; }
done
echo "OK  required scripts present"

if [[ "$META_DEPLOY_APPLY" != "1" ]]; then
  echo "DRY-RUN OK — run without META_DEPLOY_APPLY=0 to deploy"
  exit 0
fi

if [[ "$GIT_PULL" == "1" ]]; then
  echo "-- git pull --"
  git pull --ff-only origin main || git pull --ff-only
fi

if [[ "$META_UPDATE_ENV" == "1" ]]; then
  echo "-- merge safe Meta env defaults (off) --"
  merge_env_line PTT_META_ALERTS_ENABLED 0
  merge_env_line NEXT_PUBLIC_PTT_META_ALERTS_ENABLED 0
  merge_env_line PTT_META_TRACKING_ENABLED 0
  merge_env_line NEXT_PUBLIC_PTT_META_TRACKING_ENABLED 0
  merge_env_line PTT_CAPI_ENABLED 0
  merge_env_line PTT_META_CONVERSION_SYNC_ENABLED 0
  merge_env_line PTT_META_INSIGHTS_ARCHIVE_ENABLED 0
  merge_env_line PTT_LAUNCH_QA_META_STRICT 0
fi

if [[ "$META_APPLY_DDL" == "1" ]]; then
  echo "-- PostgreSQL DDL v4 (B8) --"
  bash "$ROOT/scripts/apply_pg_ddl_v4_meta_enterprise.sh"
  echo "-- PostgreSQL DDL v5 (B9) --"
  bash "$ROOT/scripts/apply_pg_ddl_v5_meta_conversion.sh"
else
  echo "SKIP DDL (META_APPLY_DDL=0)"
fi

if [[ "$META_SKIP_BUILD" != "1" ]]; then
  echo "-- Nest ptt-crm-api --"
  cd "$ROOT/services/ptt-crm-api"
  npm ci
  npm run build
  if grep -q "MetaTrackingModule" dist/app.module.js 2>/dev/null; then
    echo "OK  MetaTrackingModule in dist"
  else
    echo "FAIL MetaTrackingModule missing from Nest build"
    exit 1
  fi
  if grep -q "MetaAlertsModule" dist/app.module.js 2>/dev/null; then
    echo "OK  MetaAlertsModule in dist"
  else
    echo "FAIL MetaAlertsModule missing from Nest build"
    exit 1
  fi

  echo "-- ops-web --"
  cd "$ROOT/services/ops-web"
  npm ci
  export NEXT_PUBLIC_PTT_API_URL="$OPS_API_URL"
  npm run build
  mkdir -p .next/standalone/.next
  rm -rf .next/standalone/.next/static
  cp -r .next/static .next/standalone/.next/static
  if [[ -d public ]]; then
    rm -rf .next/standalone/public
    cp -r public .next/standalone/public
  fi

  if [[ "$META_SKIP_PORTAL" != "1" && -f "$ROOT/services/portal-web/package.json" ]]; then
    echo "-- portal-web --"
    cd "$ROOT/services/portal-web"
    npm ci
    npm run build
    mkdir -p .next/standalone/.next
    rm -rf .next/standalone/.next/static
    cp -r .next/static .next/standalone/.next/static
    if [[ -d public ]]; then
      rm -rf .next/standalone/public
      cp -r public .next/standalone/public
    fi
  fi
else
  echo "SKIP builds (META_SKIP_BUILD=1)"
fi

echo "-- restart systemd services --"
RESTARTED=0
for svc in ptt-crm-api ptt-ops-web ptt-portal-web ptt-worker; do
  if systemctl restart "$svc" 2>/dev/null; then
    echo "OK  restarted $svc"
    RESTARTED=1
  fi
done
if [[ "$RESTARTED" -eq 0 ]]; then
  echo "WARN  no systemd units restarted — run manually:"
  echo "  sudo systemctl restart ptt-crm-api ptt-ops-web ptt-portal-web ptt-worker"
fi

echo "-- wait for Nest /health --"
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:3000/health" >/dev/null 2>&1; then
    echo "OK  Nest /health"
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "WARN  Nest /health not ready — smoke may fail"
  fi
  sleep 1
done

if [[ "$META_SKIP_SMOKE" != "1" ]]; then
  echo ""
  bash "$ROOT/scripts/wave_meta_enterprise_smoke.sh"
else
  echo "SKIP smoke (META_SKIP_SMOKE=1)"
fi

echo ""
echo "Deploy complete."
echo "Manual UI checks:"
echo "  - https://<ops-host>/meta/facebook-ads  (tabs, export CSV, filters)"
echo "  - https://<ops-host>/meta/tracking      (when NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1)"
echo "  - Portal performance tab (CPL Δ, attribution footer)"
