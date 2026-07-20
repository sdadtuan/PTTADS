#!/usr/bin/env bash
# Export Email Marketing daily facts PG → ClickHouse (Wave 2 / EM-7)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"
export CLICKHOUSE_USER="${CLICKHOUSE_USER:-ptt}"
export CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-ptt_dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_EMAIL_CLICKHOUSE_EXPORT="${PTT_EMAIL_CLICKHOUSE_EXPORT:-1}"
python3 - <<'PY'
import json
import os
from ptt_email.bi_clickhouse import export_email_facts_to_clickhouse

fact_date = os.environ.get("FACT_DATE") or None
out = export_email_facts_to_clickhouse(fact_date=fact_date, skip_if_no_ch=False)
print(json.dumps(out))
if not out.get("ok") and not out.get("skipped"):
    raise SystemExit(1)
PY
