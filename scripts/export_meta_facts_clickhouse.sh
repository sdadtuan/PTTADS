#!/usr/bin/env bash
# Export Meta/Google daily_performance PG → ClickHouse (B14 / ME48)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_META_WAREHOUSE_EXPORT="${PTT_META_WAREHOUSE_EXPORT:-1}"
python3 - <<'PY'
import json
import os
from ptt_meta.warehouse_export import export_meta_facts_range, export_meta_facts_to_clickhouse

days = int(os.environ.get("EXPORT_DAYS") or "0")
fact_date = os.environ.get("FACT_DATE") or None
client_id = os.environ.get("CLIENT_ID") or None
if days > 1:
    out = export_meta_facts_range(days=days, client_id=client_id, skip_if_no_ch=False)
else:
    out = export_meta_facts_to_clickhouse(fact_date=fact_date, client_id=client_id, skip_if_no_ch=False)
print(json.dumps(out))
if not out.get("ok") and not out.get("skipped"):
    raise SystemExit(1)
PY
