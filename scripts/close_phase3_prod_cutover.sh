#!/usr/bin/env bash
# Phase 3 prod cutover orchestrator (run on VPS as deploy user after Phase 2 + QA gates)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
APPLY="${APPLY:-0}"

echo "==> Phase 3 prod cutover — preflight"
: "${DATABASE_URL:?Set DATABASE_URL}"
: "${PTT_PORTAL_JWT_SECRET:?Set PTT_PORTAL_JWT_SECRET (32+ chars)}"

export PTT_PORTAL_ALLOW_STUB=0
export PTT_PORTAL_STUB_USERS=""
export PTT_CUTOVER_ENV="${PTT_CUTOVER_ENV:-prod}"
export PTT_CUTOVER_SKIP_URL_CHECK="${PTT_CUTOVER_SKIP_URL_CHECK:-1}"
export PTT_CUTOVER_SKIP_SYSTEMD="${PTT_CUTOVER_SKIP_SYSTEMD:-$([[ "$APPLY" == "1" ]] && echo 0 || echo 1)}"

"$PYTHON" -m ptt_crm.phase3_prod_cutover_preflight || {
  echo "FAIL preflight — fix issues in .local-dev/phase3-prod-cutover-preflight.json" >&2
  exit 1
}

echo "==> DDL v3/v4 + Google sync"
./scripts/apply_pg_ddl_v3_creatives.sh
./scripts/apply_pg_ddl_v3_launch_qa.sh
./scripts/apply_pg_ddl_v3_google_sync.sh
./scripts/apply_pg_ddl_v4_hub_sop.sh

echo "==> Hub/SOP backfill (idempotent)"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-/var/www/ptt/ptt.db}"
python3 scripts/migrate_sqlite_hub_sop_to_pg.py

echo "==> Portal pilot users (scrypt)"
: "${PORTAL_PILOT_PASSWORD:?Set PORTAL_PILOT_PASSWORD for seed}"
python3 scripts/seed_portal_pilot_users.py --password "$PORTAL_PILOT_PASSWORD"

echo "==> Portal web build (standalone)"
PORTAL_DIR="$ROOT/services/portal-web"
(
  cd "$PORTAL_DIR"
  npm ci
  export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-https://api.pttads.vn}"
  npm run build
  cp -r .next/static .next/standalone/.next/static
  cp -r public .next/standalone/public 2>/dev/null || true
)

echo "==> Temporal stack"
docker compose -f docker-compose.temporal.yml up -d

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. To apply on VPS:"
  echo "  export APPLY=1"
  echo "  export PORTAL_PILOT_PASSWORD='...'"
  echo "  export DATABASE_URL='...'"
  echo "  export PTT_PORTAL_JWT_SECRET='...'"
  echo "  sudo -E $0"
  echo ""
  echo "Merge deploy/env.phase3-prod.example into /var/www/ptt/.env"
  echo "Post-cutover smoke:"
  echo "  curl -sf https://portal.pttads.vn/health"
  echo "  curl -sfI https://portal.pttads.vn/login"
  echo "  PORTAL_E2E_URL=https://portal.pttads.vn PORTAL_E2E_API_URL=https://portal.pttads.vn \\"
  echo "    ./scripts/phase3_playwright_e2e_gate.sh"
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

_set_env PTT_PORTAL_ALLOW_STUB "0"
_set_env PTT_PORTAL_STUB_USERS ""
_set_env PTT_HUB_READ_SOURCE "${PTT_HUB_READ_SOURCE:-1}"
_set_env PTT_SOP_READ_SOURCE "${PTT_SOP_READ_SOURCE:-1}"
_set_env PTT_TEMPORAL_ADDRESS "${PTT_TEMPORAL_ADDRESS:-127.0.0.1:7233}"
_set_env PTT_TEMPORAL_NAMESPACE "${PTT_TEMPORAL_NAMESPACE:-default}"
_set_env PTT_TEMPORAL_TASK_QUEUE "${PTT_TEMPORAL_TASK_QUEUE:-ptt-agency}"
_set_env NEXT_PUBLIC_PTT_API_URL "${NEXT_PUBLIC_PTT_API_URL:-https://portal.pttads.vn}"
_set_env PORTAL_PORT "${PORTAL_PORT:-3100}"
_set_env PTT_PORTAL_CORS_ORIGINS "${PTT_PORTAL_CORS_ORIGINS:-https://portal.pttads.vn}"

echo "==> Systemd units (portal, worker, google timer)"
if [[ "$(id -u)" -eq 0 ]]; then
  ./scripts/install_phase3_systemd.sh
  ./scripts/certbot_portal_vps.sh
  systemctl restart ptt-portal-web ptt-temporal-worker ptt-crm-api 2>/dev/null || true
  systemctl enable --now ptt-google-insights.timer 2>/dev/null || true
else
  echo "WARN  Run as root on VPS for certbot + systemd: sudo -E APPLY=1 $0"
  exit 1
fi

echo "==> Post-cutover smoke"
curl -sf "${PTT_PROD_API_URL:-https://api.pttads.vn}/health" >/dev/null
curl -sfI "${PTT_PROD_PORTAL_URL:-https://portal.pttads.vn}/login" >/dev/null

echo "OK  Phase 3 prod cutover applied. Complete UAT: docs/runbooks/phase3-uat-signoff.md"
