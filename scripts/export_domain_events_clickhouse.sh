#!/usr/bin/env bash
# Export PG domain_events → ClickHouse (Phase 4 F4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
SINCE="${1:-}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi

cd "$ROOT"
if [[ -n "$SINCE" ]]; then export SINCE; fi
exec "$PYTHON" -c "
from ptt_analytics.clickhouse_export import export_to_clickhouse
import json, os
print(json.dumps(export_to_clickhouse(since=os.environ.get('SINCE'))))
"
