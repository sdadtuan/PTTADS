#!/usr/bin/env bash
# Meta Enterprise B10 — daily_performance insight_level / adset DDL v6
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply DDL v6 Meta Insights Level (B10)"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import apply_ddl_v6_meta_insights_level, pg_daily_performance_insight_level_ready, pg_v3_ready
assert pg_v3_ready(), 'Apply v3 performance first'
apply_ddl_v6_meta_insights_level()
assert pg_daily_performance_insight_level_ready(), 'insight_level column missing on daily_performance'
print('OK  DDL v6 Meta Insights Level applied')
"
