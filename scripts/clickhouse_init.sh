#!/usr/bin/env bash
# Initialize ClickHouse schema for domain_events (Phase 4 F4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
CONTAINER="${CLICKHOUSE_CONTAINER:-ptt-clickhouse}"

cd "$ROOT"

if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker exec -i "$CONTAINER" clickhouse-client \
    --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" \
    --multiquery < deploy/clickhouse/init-domain-events.sql
  echo '{"ok": true, "via": "clickhouse-client"}'
else
  PYTHON="${PYTHON:-python3}"
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi
  export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
  "$PYTHON" -c "
from ptt_analytics.clickhouse_export import clickhouse_init_schema
import json
print(json.dumps(clickhouse_init_schema()))
"
fi
