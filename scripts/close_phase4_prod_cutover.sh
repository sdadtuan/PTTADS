#!/usr/bin/env bash
# Phase 4 prod cutover — Flask readonly + campaign writes + ClickHouse + Meta pilot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

echo "==> Phase 4 prod cutover — preflight"
: "${DATABASE_URL:?Set DATABASE_URL}"

APPLY="${APPLY:-0}"
FLASK_MODE="${PTT_FLASK_MONOLITH_MODE:-readonly}"
META_STUB="${PTT_META_CAMPAIGN_WRITE_STUB:-0}"
META_PILOT="${PTT_META_CAMPAIGN_WRITE_PILOT:-1}"
export PTT_CUTOVER_ENV="${PTT_CUTOVER_ENV:-prod}"
export PTT_CUTOVER_SKIP_PILOT="${PTT_CUTOVER_SKIP_PILOT:-$([[ "$APPLY" == "1" ]] && echo 0 || echo 1)}"

echo "    PTT_FLASK_MONOLITH_MODE=$FLASK_MODE"
echo "    PTT_META_CAMPAIGN_WRITE_STUB=$META_STUB"
echo "    PTT_META_CAMPAIGN_WRITE_PILOT=$META_PILOT"

if [[ "$PTT_CUTOVER_SKIP_PILOT" != "1" ]]; then
  export PTT_FLASK_MONOLITH_MODE="$FLASK_MODE"
  export PTT_META_CAMPAIGN_WRITE_STUB="$META_STUB"
  export PTT_META_CAMPAIGN_WRITE_PILOT="$META_PILOT"
fi

"$PYTHON" -m ptt_crm.phase4_prod_cutover_preflight || {
  echo "FAIL preflight — see .local-dev/phase4-prod-cutover-preflight.json" >&2
  exit 1
}

echo "==> DDL v5 campaign writes"
./scripts/apply_pg_ddl_v5_campaign_writes.sh

echo "==> ClickHouse stack + schema"
docker compose -f docker-compose.clickhouse.yml up -d
./scripts/clickhouse_init.sh

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. To apply prod env + systemd on VPS:"
  echo "  export APPLY=1"
  echo "  export PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=<uuid>"
  echo "  export PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<meta_campaign_id>"
  echo "  sudo -E $0"
  echo ""
  echo "Add to /var/www/ptt/.env (see deploy/env.phase4-prod.example):"
  echo "  PTT_FLASK_MONOLITH_MODE=$FLASK_MODE"
  echo "  PTT_META_CAMPAIGN_WRITE_STUB=$META_STUB"
  echo "  PTT_META_CAMPAIGN_WRITE_PILOT=$META_PILOT"
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

_set_env PTT_FLASK_MONOLITH_MODE "$FLASK_MODE"
_set_env PTT_META_CAMPAIGN_WRITE_STUB "$META_STUB"
_set_env PTT_META_CAMPAIGN_WRITE_PILOT "$META_PILOT"
_set_env CLICKHOUSE_URL "${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
_set_env CLICKHOUSE_USER "${CLICKHOUSE_USER:-ptt}"
_set_env CLICKHOUSE_PASSWORD "${CLICKHOUSE_PASSWORD:-ptt_dev}"
if [[ -n "${PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS:-}" ]]; then
  _set_env PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS "$PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS"
fi
if [[ -n "${PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS:-}" ]]; then
  _set_env PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS "$PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS"
fi

if [[ "$(id -u)" -eq 0 ]]; then
  cp -f deploy/ptt-clickhouse-export.service /etc/systemd/system/ 2>/dev/null || true
  cp -f deploy/ptt-clickhouse-export.timer /etc/systemd/system/ 2>/dev/null || true
  systemctl daemon-reload
  systemctl enable --now ptt-clickhouse-export.timer 2>/dev/null || true
  systemctl restart ptt ptt-crm-api ptt-temporal-worker 2>/dev/null || true
else
  echo "WARN  Run with sudo for systemd restart: sudo -E APPLY=1 $0"
  exit 1
fi

echo "==> Smoke export"
SINCE_ISO="$(python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
./scripts/export_domain_events_clickhouse.sh "$SINCE_ISO"

echo "OK  Phase 4 prod cutover applied. Runbook: docs/runbooks/phase4-prod-cutover-checklist.md"
