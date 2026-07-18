#!/usr/bin/env bash
# Meta long-lived token refresh + 7-day expiry alerts (Phase 2 M1-03)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_META_TOKEN_REFRESH="${PTT_META_TOKEN_REFRESH:-1}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"
cd "$ROOT"
echo "==> Meta token refresh (dry_run=$DRY_RUN force=$FORCE stub=${PTT_META_TOKEN_REFRESH_STUB:-0})"
"$PYTHON" -c "
from ptt_meta.token_refresh import sync_meta_token_refresh
import json
dry = '${DRY_RUN}' in ('1', 'true', 'yes')
force = '${FORCE}' in ('1', 'true', 'yes')
out = sync_meta_token_refresh(dry_run=dry, force=force)
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
