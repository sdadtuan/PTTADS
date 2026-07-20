#!/usr/bin/env bash
# Sync SQLite lead rules → PG crm_ingest_rules_snapshot (Phase 2 ingest cutover)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_LEAD_INGEST_RULES_SOURCE="${PTT_LEAD_INGEST_RULES_SOURCE:-pg}"

cd "$ROOT"
"$PYTHON" -c "
from ptt_crm.phase2_prereqs import ensure_ingest_rules_snapshot
import json
out = ensure_ingest_rules_snapshot(sync_from_sqlite=True)
print(json.dumps(out, indent=2, default=str))
if not out.get('ok'):
    raise SystemExit(1)
print('OK  ingest rules snapshot synced')
"
