#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/.local-dev"

stop_pid() {
  local name="$1"
  local file="$LOG_DIR/${name}.pid"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "==> Stopped $name pid=$pid"
    fi
    rm -f "$file"
  fi
}

stop_pid flask
stop_pid worker
stop_pid sla_cron

if command -v docker >/dev/null 2>&1 && [[ -f "$ROOT/docker-compose.yml" ]]; then
  if docker compose ps -q postgres 2>/dev/null | grep -q .; then
    echo "==> docker compose down (optional — comment out to keep PG running)"
    # docker compose down
  fi
fi

echo "==> Local dev stopped"
