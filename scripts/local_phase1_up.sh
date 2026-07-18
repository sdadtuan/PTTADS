#!/usr/bin/env bash
# PTT Agency Phase 1 — local dev orchestrator
# Usage:
#   ./scripts/local_phase1_up.sh          # auto-detect mode
#   ./scripts/local_phase1_up.sh docker   # force docker compose
#   ./scripts/local_phase1_up.sh brew     # Homebrew PostgreSQL
#   ./scripts/local_phase1_up.sh lite     # sync fallback (no PG)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-auto}"
LOG_DIR="$ROOT/.local-dev"
mkdir -p "$LOG_DIR"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

export PORT="${PORT:-5050}"
export FLASK_DEBUG="${FLASK_DEBUG:-0}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
export PTT_WEBHOOK_V1_ENQUEUE="${PTT_WEBHOOK_V1_ENQUEUE:-1}"
export PTT_JOBS_SYNC_FALLBACK="${PTT_JOBS_SYNC_FALLBACK:-1}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"

_detect_mode() {
  if [[ "$MODE" != "auto" ]]; then
    echo "$MODE"
    return
  fi
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "docker"
  elif command -v psql >/dev/null 2>&1 && psql "$DATABASE_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "brew"
  else
    echo "lite"
  fi
}

MODE="$(_detect_mode)"
echo "==> PTT local Phase 1 mode: $MODE"

"$PYTHON" -m pip install -q -r requirements.txt

_start_docker() {
  echo "==> Starting docker compose (postgres, redis, rabbitmq)..."
  docker compose up -d
  echo "==> Waiting for postgres..."
  for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U ptt -d ptt_agency >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
}

_start_brew_pg() {
  echo "==> Using Homebrew PostgreSQL at $DATABASE_URL"
  if ! psql "$DATABASE_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "ERROR: PostgreSQL not reachable. Install:"
    echo "  brew install postgresql@15"
    echo "  brew services start postgresql@15"
    echo "  createuser -s ptt || true"
    echo "  createdb -O ptt ptt_agency || true"
    echo "  psql -f docs/specs/2026-07-17-postgresql-ddl-v1.sql postgres"
    exit 1
  fi
  psql "$DATABASE_URL" -f docs/specs/2026-07-17-postgresql-ddl-v1.sql >/dev/null 2>&1 || true
}

_apply_pg_ddl_v2() {
  if [[ "$MODE" == "lite" ]]; then
    return
  fi
  if [[ -x "$ROOT/scripts/apply_pg_ddl_v2_leads.sh" ]]; then
    echo "==> Applying PG DDL v2 (crm_leads read replica)..."
    "$ROOT/scripts/apply_pg_ddl_v2_leads.sh" >/dev/null 2>&1 || echo "WARN: DDL v2 apply skipped (see apply_pg_ddl_v2_leads.sh)"
  fi
}

_lite_notice() {
  echo ""
  echo "==> LITE mode: PostgreSQL/Docker không có — webhook ingest SYNC (không queue)."
  echo "    Cài Docker Desktop hoặc PostgreSQL để test đầy đủ worker + job_queue."
  echo "    https://docs.docker.com/desktop/install/mac-install/"
  echo ""
}

_start_flask() {
  if [[ -f "$LOG_DIR/flask.pid" ]] && kill -0 "$(cat "$LOG_DIR/flask.pid")" 2>/dev/null; then
    echo "==> Restarting Flask (pid=$(cat "$LOG_DIR/flask.pid")) ..."
    kill "$(cat "$LOG_DIR/flask.pid")" 2>/dev/null || true
    sleep 1
    rm -f "$LOG_DIR/flask.pid"
  fi
  echo "==> Starting Flask on :$PORT ..."
  nohup env FLASK_DEBUG="$FLASK_DEBUG" "$PYTHON" app.py >>"$LOG_DIR/flask.log" 2>&1 &
  echo $! >"$LOG_DIR/flask.pid"
  disown 2>/dev/null || true
  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then
      echo "==> Flask ready (${i}s)"
      return
    fi
    sleep 1
  done
  echo "WARN: Flask healthz timeout — see $LOG_DIR/flask.log"
}

_start_worker() {
  if [[ "$MODE" == "lite" ]]; then
    echo "==> Skipping worker (lite mode)"
    return
  fi
  if ! "$PYTHON" -c "from ptt_jobs.db import pg_available; import sys; sys.exit(0 if pg_available() else 1)" 2>/dev/null; then
    echo "==> PostgreSQL unavailable — worker skipped"
    return
  fi
  if [[ -f "$LOG_DIR/worker.pid" ]] && kill -0 "$(cat "$LOG_DIR/worker.pid")" 2>/dev/null; then
    echo "==> Restarting ptt-worker (pid=$(cat "$LOG_DIR/worker.pid")) ..."
    kill "$(cat "$LOG_DIR/worker.pid")" 2>/dev/null || true
    sleep 1
    rm -f "$LOG_DIR/worker.pid"
  fi
  echo "==> Starting ptt-worker ..."
  nohup "$PYTHON" -m ptt_worker >"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$LOG_DIR/worker.pid"
}

_start_sla_cron() {
  if [[ "${PTT_SLA_CRON_ENABLED:-1}" != "1" ]]; then
    echo "==> SLA cron disabled (PTT_SLA_CRON_ENABLED=0)"
    return
  fi
  if [[ -f "$LOG_DIR/sla_cron.pid" ]] && kill -0 "$(cat "$LOG_DIR/sla_cron.pid")" 2>/dev/null; then
    echo "==> SLA cron already running pid=$(cat "$LOG_DIR/sla_cron.pid")"
    return
  fi
  chmod +x "$ROOT/scripts/local_sla_cron.sh"
  echo "==> Starting SLA cron (every ${PTT_SLA_CRON_INTERVAL_SEC:-300}s) ..."
  nohup "$ROOT/scripts/local_sla_cron.sh" >>"$LOG_DIR/sla_cron.log" 2>&1 &
  echo $! >"$LOG_DIR/sla_cron.pid"
}

case "$MODE" in
  docker) _start_docker ;;
  brew)   _start_brew_pg ;;
  lite)   _lite_notice ;;
  *) echo "Unknown mode: $MODE"; exit 1 ;;
esac

_apply_pg_ddl_v2

_start_flask
_start_worker
_start_sla_cron

echo ""
echo "==> Local stack up (mode=$MODE)"
echo "    App:    http://127.0.0.1:$PORT/"
echo "    Health: http://127.0.0.1:$PORT/healthz"
echo "    Worker: http://127.0.0.1:$PORT/health/worker"
echo "    Agency: http://127.0.0.1:$PORT/crm/agency"
echo "    API:    http://127.0.0.1:$PORT/api/v1/channels"
echo "    Logs:   $LOG_DIR/flask.log  $LOG_DIR/worker.log  $LOG_DIR/sla_cron.log"
echo "    Smoke:  ./scripts/local_phase1_smoke.sh"
echo "    Stop:   ./scripts/local_phase1_down.sh"
