#!/usr/bin/env bash
# Meta insights sync → daily_performance (Phase 2 M2)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_META_INSIGHTS_SYNC="${PTT_META_INSIGHTS_SYNC:-1}"
TARGET_DATE="${1:-}"
STUB="${PTT_META_INSIGHTS_STUB:-0}"
cd "$ROOT"
echo "==> Meta insights sync (date=${TARGET_DATE:-T-1} stub=$STUB)"
"$PYTHON" -c "
from ptt_meta.insights_sync import sync_meta_insights
import json
import os
target = '${TARGET_DATE}' or None
out = sync_meta_insights(target_date=target)
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
