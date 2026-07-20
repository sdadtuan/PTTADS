#!/usr/bin/env bash
# EM-0 — apply email_mkt PostgreSQL schema (requires clients DDL v1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

echo "==> Pre-check: clients table exists"
"$PYTHON" - <<'PY'
import os
import sys
import psycopg2

url = os.environ["DATABASE_URL"]
conn = psycopg2.connect(url)
cur = conn.cursor()
try:
    cur.execute("SELECT 1 FROM clients LIMIT 1")
except Exception as exc:
    print(f"FAIL  clients table missing — apply postgresql-ddl-v1 first: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    cur.close()
    conn.close()
print("OK  clients table present")
PY

echo "==> Apply email_mkt DDL"
"$PYTHON" - <<PY
import os
import sys
from pathlib import Path
import psycopg2

root = Path("$ROOT")
sql_path = root / "deploy/sql/email_mkt_pg_schema.sql"
sql = sql_path.read_text(encoding="utf-8")
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
try:
    cur.execute(sql)
except Exception as exc:
    print(f"FAIL  apply email_mkt schema: {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    cur.close()
    conn.close()
print("OK  email_mkt schema applied")
PY

echo "==> Verify schema_migrations"
"$PYTHON" - <<'PY'
import os
import sys
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute(
    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
    ("email_mkt_v1",),
)
if cur.fetchone() is None:
    print("FAIL  schema_migrations email_mkt_v1 missing", file=sys.stderr)
    sys.exit(1)
cur.execute("SELECT COUNT(*) FROM email_mkt.rules WHERE scope = 'global'")
count = cur.fetchone()[0]
cur.close()
conn.close()
print(f"OK  email_mkt_v1 migration recorded · {count} global rules seeded")
PY
