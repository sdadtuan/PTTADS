#!/usr/bin/env bash
# Wave B1 — ensure Agency PG tables (DDL v1 onboarding + KPI seed).
# Safe to re-run (idempotent). No sudo required.
#
# Usage on VPS:
#   cd /var/www/ptt && set -a && source .env && set +a
#   ./scripts/wave_b1_pg_bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL in .env}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi

cd "$ROOT"

echo "== Wave B1 PG bootstrap =="
echo "DATABASE_URL=${DATABASE_URL%%@*}@***"

"$PYTHON" <<'PY'
from pathlib import Path

from ptt_crm.pg_schema import (
    _apply_sql_file,
    apply_kpi_dictionary_seed,
    pg_kpi_definitions_ready,
)
from ptt_jobs.db import pg_connection, pg_available

root = Path(".")
if not pg_available():
    raise SystemExit("FAIL  PostgreSQL unavailable — check DATABASE_URL")

v1 = root / "docs/specs/2026-07-17-postgresql-ddl-v1.sql"
if not v1.is_file():
    raise SystemExit(f"FAIL  missing {v1}")

print("-- apply DDL v1 (clients, onboarding, kpi, jobs…) --")
_apply_sql_file(v1)

print("-- KPI dictionary seed --")
apply_kpi_dictionary_seed()
if not pg_kpi_definitions_ready(min_rows=1):
    raise SystemExit("FAIL  kpi_definitions not ready after seed")

print("-- seed onboarding checklist for all clients --")
with pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM clients ORDER BY code")
        client_ids = [r[0] for r in cur.fetchall()]
        for cid in client_ids:
            cur.execute("SELECT seed_client_onboarding(%s::uuid)", (cid,))
        cur.execute(
            """
            SELECT COUNT(*)::int FROM client_onboarding_items
            """
        )
        item_count = int(cur.fetchone()[0] or 0)
    conn.commit()

print(f"OK  clients={len(client_ids)} onboarding_items={item_count}")
print(f"OK  kpi_definitions ready")
PY

echo ""
echo "Next: ./scripts/wave_b1_smoke.sh"
