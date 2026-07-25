#!/usr/bin/env bash
# Prod-Z4 — campaign_write_requests channel=zalo
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DDL="$ROOT/docs/specs/2026-07-26-postgresql-ddl-z4-campaign-writes.sql"
: "${DATABASE_URL:?DATABASE_URL required}"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$DDL"
echo "Applied Z4 campaign-writes DDL"
