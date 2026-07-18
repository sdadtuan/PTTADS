#!/usr/bin/env bash
# Staging closed-loop pilot — 1 client: token + pixel + hub map + insights → CPL tab (P0 #4)
#
# Prereqs: DDL v3, client in PG, Hub campaign mapped (stub: external_campaign_id=stub_campaign_1)
#
# Usage:
#   set -a && source deploy/env.staging-closed-loop-pilot.example && set +a
#   ./scripts/seed_meta_channel_account.py
#   ./scripts/sync_hub_campaign_map.sh
#   ./scripts/staging_closed_loop_pilot.sh --sync
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_META_INSIGHTS_SYNC="${PTT_META_INSIGHTS_SYNC:-1}"
export PTT_META_INSIGHTS_STUB="${PTT_META_INSIGHTS_STUB:-1}"
exec "$PYTHON" "$ROOT/scripts/staging_closed_loop_pilot.py" "$@"
