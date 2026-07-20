#!/usr/bin/env bash
# Apply staff auth DDL (Phase 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
DDL="$ROOT/docs/specs/2026-07-20-postgresql-ddl-staff-auth.sql"
echo "==> Apply staff auth DDL"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$DDL"
echo "OK"
