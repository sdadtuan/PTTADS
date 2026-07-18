#!/usr/bin/env bash
# Backfill SQLite crm_leads → PostgreSQL read replica
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_LEAD_REPLICA_SYNC="${PTT_LEAD_REPLICA_SYNC:-1}"
cd "$ROOT"
echo "==> Lead replica full backfill"
"$PYTHON" -c "from ptt_crm.lead_sync import sync_full_backfill; import json; print(json.dumps(sync_full_backfill(), indent=2))"
