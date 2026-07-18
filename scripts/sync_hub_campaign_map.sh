#!/usr/bin/env bash
# Seed / sync Hub SQLite campaigns → PG hub_campaign_map (Phase 2 P0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
INCLUDE_INACTIVE="${INCLUDE_INACTIVE:-0}"
cd "$ROOT"
echo "==> Sync hub_campaign_map from SQLite (include_inactive=$INCLUDE_INACTIVE)"
"$PYTHON" -c "
from ptt_agency.hub_campaign_sync import sync_all_from_sqlite
from ptt_jobs.config import sqlite_db_path
import json
inc = '${INCLUDE_INACTIVE}' in ('1', 'true', 'yes')
out = sync_all_from_sqlite(sqlite_path=sqlite_db_path(), include_inactive=inc)
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True):
    raise SystemExit(1)
"
