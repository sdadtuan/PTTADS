#!/usr/bin/env bash
# Phase 5 prod cutover — staged feature flags (governance → portal → experiments)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

echo "==> Phase 5 prod cutover — preflight"
: "${DATABASE_URL:?Set DATABASE_URL}"
export SEO_AEO_DB="${SEO_AEO_DB:-pg}"

APPLY="${APPLY:-0}"
ENABLE_GOV="${PHASE5_ENABLE_GOVERNANCE:-1}"
ENABLE_PORTAL="${PHASE5_ENABLE_PORTAL:-0}"
ENABLE_EXP="${PHASE5_ENABLE_EXPERIMENTS:-0}"
TOKEN="${PTT_PORTAL_SEO_SERVICE_TOKEN:-}"
FLASK_URL="${PTT_FLASK_MONOLITH_URL:-http://127.0.0.1:8002}"

echo "    PTT_SEO_GOVERNANCE_ENABLED=$ENABLE_GOV"
echo "    PTT_PORTAL_SEO_ENABLED=$ENABLE_PORTAL"
echo "    PTT_SEO_EXPERIMENTS_ENABLED=$ENABLE_EXP"

export PTT_SEO_GOVERNANCE_ENABLED="$ENABLE_GOV"
export PTT_SEO_EXPERIMENTS_ENABLED="$ENABLE_EXP"
export PTT_PORTAL_SEO_ENABLED="$ENABLE_PORTAL"
export PHASE5_EXPECT_GOVERNANCE="$ENABLE_GOV"
export PHASE5_EXPECT_PORTAL="$ENABLE_PORTAL"
export PHASE5_EXPECT_EXPERIMENTS="$ENABLE_EXP"
export PHASE5_SKIP_SOAK=1
export PHASE5_SKIP_PORTAL_SIGNOFF="${PHASE5_SKIP_PORTAL_SIGNOFF:-1}"

echo "==> Phase 5 gate (pre-cutover)"
"$PYTHON" -m ptt_crm.phase5_prod_gates || {
  echo "FAIL gate — fix tests before cutover" >&2
  exit 1
}

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. Staged prod rollout:"
  echo "  1) PHASE5_ENABLE_GOVERNANCE=1 APPLY=1 sudo -E $0"
  echo "  2) After portal UAT: PHASE5_ENABLE_PORTAL=1 PHASE5_SKIP_PORTAL_SIGNOFF=0 APPLY=1 sudo -E $0"
  echo "  3) Internal team: PHASE5_ENABLE_EXPERIMENTS=1 APPLY=1 sudo -E $0"
  echo ""
  echo "See deploy/env.phase5-prod.example and docs/runbooks/seo-aeo-pg-oauth-uat-cutover.md §10"
  exit 0
fi

ENV_FILE="${PTT_ENV_FILE:-/var/www/ptt/.env}"
touch "$ENV_FILE"

_set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >>"$ENV_FILE"
  fi
}

_set_env SEO_AEO_DB "${SEO_AEO_DB:-pg}"
_set_env PTT_SEO_GOVERNANCE_ENABLED "$ENABLE_GOV"
_set_env PTT_PORTAL_SEO_ENABLED "$ENABLE_PORTAL"
_set_env PTT_SEO_EXPERIMENTS_ENABLED "$ENABLE_EXP"
if [[ -n "$TOKEN" ]]; then
  _set_env PTT_PORTAL_SEO_SERVICE_TOKEN "$TOKEN"
fi
if [[ -n "$FLASK_URL" ]]; then
  _set_env PTT_FLASK_MONOLITH_URL "$FLASK_URL"
fi

if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart ptt ptt-crm-api 2>/dev/null || true
else
  echo "WARN  Run with sudo for systemd restart: sudo -E APPLY=1 $0"
  exit 1
fi

echo "==> Soak record (day 0)"
"$ROOT/scripts/phase5_soak_record.sh" || true

echo "OK  Phase 5 flags applied. Daily soak: ./scripts/phase5_soak_record.sh (≥7 days)"
echo "    Evaluate: PHASE5_SKIP_SOAK=0 ./scripts/phase5_prod_cutover_gate.sh"
