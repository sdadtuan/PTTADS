#!/usr/bin/env bash
# Start Staging Phase 3 stack (Postgres + Nest + optional Portal + Temporal)
#
# Usage:
#   set -a && source deploy/env.staging-phase3.example && set +a
#   ./scripts/staging_phase3_up.sh              # postgres + nest + temporal
#   ./scripts/staging_phase3_up.sh --portal     # + portal-web :3100
#   ./scripts/staging_phase3_up.sh --nest-only  # nest only (postgres assumed up)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-$PTT_API_URL}"
export PORTAL_PORT="${PORTAL_PORT:-3100}"

_start_postgres() {
  if command -v docker >/dev/null 2>&1; then
    echo "==> Postgres (docker compose)"
    docker compose up -d postgres
    for _ in $(seq 1 30); do
      if docker compose exec -T postgres pg_isready -U ptt -d ptt_agency >/dev/null 2>&1; then
        echo "OK  Postgres ready"
        return 0
      fi
      sleep 1
    done
    echo "WARN Postgres not ready yet" >&2
  fi
}

_start_temporal() {
  if [[ "$MODE" == "--nest-only" ]] || [[ "$MODE" == "--portal" ]]; then
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "==> Temporal (docker compose)"
    docker compose -f docker-compose.temporal.yml up -d
  fi
}

case "$MODE" in
  --nest-only)
    echo "==> Nest CRM API only"
    exec "$ROOT/scripts/local_crm_api_up.sh"
    ;;
  --portal)
    _start_postgres
    echo "==> Nest (background) + Portal (foreground)"
    "$ROOT/scripts/local_crm_api_up.sh" &
    NEST_PID=$!
    trap 'kill $NEST_PID 2>/dev/null || true' EXIT
    sleep 5
    exec "$ROOT/scripts/local_portal_up.sh"
    ;;
  --help|-h)
    echo "Usage: staging_phase3_up.sh [--nest-only|--portal|--help]"
    exit 0
    ;;
  *)
    _start_postgres
    _start_temporal
    echo "==> Nest CRM API (foreground — Ctrl+C to stop)"
    echo "    Portal: ./scripts/staging_phase3_up.sh --portal"
    echo "    Gates:  ./scripts/staging_phase3_gate_pack.sh"
    exec "$ROOT/scripts/local_crm_api_up.sh"
    ;;
esac
