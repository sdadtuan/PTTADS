#!/usr/bin/env bash
# Phase 3 Hub PG migration gate (Track D1–D4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export HUB_GATE_CLIENT_ID="${HUB_GATE_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PTT_HUB_READ_SOURCE="${PTT_HUB_READ_SOURCE:-1}"
export PTT_SOP_READ_SOURCE="${PTT_SOP_READ_SOURCE:-1}"
export PTT_HUB_PG_PRIMARY="${PTT_HUB_PG_PRIMARY:-1}"
export PTT_LEAD_SHADOW_SYNC="${PTT_LEAD_SHADOW_SYNC:-0}"
cd "$ROOT"

echo "==> Ensure local Postgres (docker compose)"
if ! docker compose ps postgres 2>/dev/null | grep -q 'running'; then
  docker compose up -d postgres
  for _ in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U ptt -d ptt_agency >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "==> Apply PG v3 base + DDL v4 Hub/SOP"
./scripts/apply_pg_ddl_v3.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v4_hub_sop.sh

echo "==> Seed SQLite Hub/SOP gate data"
"$PYTHON" scripts/seed_hub_migration_gate_data.py

echo "==> One-way SQLite → PG backfill (D2)"
"$PYTHON" scripts/migrate_sqlite_hub_sop_to_pg.py

echo "==> Seed hub_campaign_map (Google pilot map for D1 CRUD check)"
"$PYTHON" scripts/seed_google_pilot_client.py 2>/dev/null || true

echo "==> Hub PG migration gate pack"
"$PYTHON" -m ptt_crm.phase3_hub_migration_gates
