#!/usr/bin/env bash
# Apply Wave B4 funnel PG DDL (S0 prep — Nest still SQLite bridge by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

URL="${DATABASE_URL:-}"
if [[ -z "$URL" ]]; then
  echo "Set DATABASE_URL in .env" >&2
  exit 1
fi

DDL="$ROOT/docs/specs/2026-07-23-wave-b4-funnel-pg-ddl.sql"
echo "Applying Wave B4 funnel DDL..."
psql "$URL" -v ON_ERROR_STOP=1 -f "$DDL"
echo "OK  Wave B4 PG DDL applied (Nest funnel still SQLite until PTT_CRM_LEADS_FUNNEL_PG=1)"
