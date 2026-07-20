#!/usr/bin/env bash
# EM-11 — apply journey execution extension (requires email_mkt_em3)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Pre-check: email_mkt_em3"
"$PYTHON" - <<'PY'
import os, sys, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1", ("email_mkt_em3",))
if cur.fetchone() is None:
    print("FAIL  apply email_mkt_em3 first: ./scripts/apply_pg_ddl_email_mkt_em3.sh", file=sys.stderr)
    sys.exit(1)
cur.close()
conn.close()
print("OK  email_mkt_em3 present")
PY

echo "==> Apply EM-11 journey execution"
"$PYTHON" - <<PY
import os, sys
from pathlib import Path
import psycopg2
sql = Path("$ROOT/deploy/sql/email_mkt_em11_journey_exec.sql").read_text(encoding="utf-8")
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
try:
    cur.execute(sql)
except Exception as exc:
    print(f"FAIL  {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    cur.close()
    conn.close()
print("OK  email_mkt_em11 extension applied")
PY
