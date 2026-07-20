#!/usr/bin/env bash
# Apply Gate D DDL (seo_cwv_snapshots, seo_crawl_import_log) — SQLite tests or PG staging/prod
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

echo "==> Apply SEO Gate D schema (SEO_AEO_DB=${SEO_AEO_DB:-sqlite})"
"$PYTHON" -c "
import os
mode = (os.environ.get('SEO_AEO_DB') or 'sqlite').strip().lower()
if mode in ('pg', 'dual'):
    from ptt_jobs.db import pg_connection
    from ptt_seo.gate_d_schema import ensure_gate_d_pg_schema
    with pg_connection() as pg:
        ensure_gate_d_pg_schema(pg)
    print('OK  Gate D PG schema applied')
else:
    import sqlite3
    from ptt_seo.gate_d_schema import ensure_gate_d_schema
    path = os.environ.get('PTT_SQLITE_PATH') or 'ptt.db'
    conn = sqlite3.connect(path)
    ensure_gate_d_schema(conn)
    conn.close()
    print(f'OK  Gate D SQLite schema applied ({path})')
"
