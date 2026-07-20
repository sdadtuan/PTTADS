#!/usr/bin/env bash
# Export SEO daily facts PG → ClickHouse (Phase 5D / enterprise BI)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
export SEO_AEO_DB="${SEO_AEO_DB:-sqlite}"
python3 - <<'PY'
import json
import os
from ptt_seo.db import seo_read
from ptt_seo.bi_clickhouse import export_seo_facts_to_clickhouse

fact_date = os.environ.get("FACT_DATE") or None
with seo_read() as conn:
    out = export_seo_facts_to_clickhouse(conn, fact_date=fact_date, skip_if_no_ch=False)
print(json.dumps(out))
if not out.get("ok") and not out.get("skipped"):
    raise SystemExit(1)
PY
