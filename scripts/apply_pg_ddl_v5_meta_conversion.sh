#!/usr/bin/env bash
# Meta Enterprise B9 — meta_conversion_rules DDL v5
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Apply DDL v5 Meta Conversion (B9)"
cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.pg_schema import (
    apply_ddl_v5_meta_conversion,
    pg_meta_alerts_ready,
    pg_meta_conversion_rules_ready,
)
assert pg_meta_alerts_ready(), 'Apply v4 first: ./scripts/apply_pg_ddl_v4_meta_enterprise.sh'
apply_ddl_v5_meta_conversion()
assert pg_meta_conversion_rules_ready(), 'meta_conversion_rules table missing'
print('OK  DDL v5 Meta Conversion applied')
"
