#!/usr/bin/env bash
# End-to-end: PG domain_events → ClickHouse export (Phase 4 F4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi

echo "==> Start ClickHouse"
docker compose -f docker-compose.clickhouse.yml up -d --force-recreate

echo "==> Wait for ClickHouse HTTP"
for i in $(seq 1 90); do
  if curl -sf -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/?query=SELECT%201" 2>/dev/null | grep -q '^1$'; then
    break
  fi
  sleep 2
done
curl -sf -u "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" "${CLICKHOUSE_URL}/?query=SELECT%201" | grep -q '^1$' || {
  echo "FAIL ClickHouse not ready at $CLICKHOUSE_URL" >&2
  docker logs ptt-clickhouse --tail 30 >&2 || true
  exit 1
}

echo "==> Init schema"
./scripts/clickhouse_init.sh

echo "==> Seed PG smoke event + export"
export PYTHONPATH="$ROOT"
"$PYTHON" -c "
from ptt_analytics.clickhouse_export import (
    seed_test_domain_event,
    export_to_clickhouse,
    clickhouse_count,
)
import json

before = clickhouse_count()
eid = seed_test_domain_event()
out = export_to_clickhouse(since='1970-01-01T00:00:00Z')
after = clickhouse_count()
assert out['exported'] >= 1, out
assert after > before, {'before': before, 'after': after, 'eid': eid}
print(json.dumps({'ok': True, 'before': before, 'after': after, 'exported': out['exported'], 'event_id': eid}))
"

echo "OK  ClickHouse export e2e passed"
