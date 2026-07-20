#!/usr/bin/env bash
# Apply Gate E DDL (OKR, crawl schedules, GA4 revenue columns) — SQLite or PG staging/prod
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "==> Apply SEO Gate E schema (SEO_AEO_DB=${SEO_AEO_DB:-sqlite})"
"$PYTHON" -c "
import os
mode = (os.environ.get('SEO_AEO_DB') or 'sqlite').strip().lower()
if mode in ('pg', 'dual'):
    from ptt_jobs.db import pg_connection
    from ptt_seo.pg_schema import ensure_pg_schema
    from ptt_seo.gate_e_schema import ensure_gate_e_pg_schema
    with pg_connection() as pg:
        ensure_pg_schema(pg)
        ensure_gate_e_pg_schema(pg)
    print('OK  Gate E PG schema applied')
else:
    import sqlite3
    from ptt_seo.gate_e_schema import ensure_gate_e_schema
    from ptt_seo.schema import ensure_schema
    path = os.environ.get('PTT_SQLITE_PATH') or 'ptt.db'
    conn = sqlite3.connect(path)
    ensure_schema(conn)
    ensure_gate_e_schema(conn)
    conn.close()
    print(f'OK  Gate E SQLite schema applied ({path})')
"
