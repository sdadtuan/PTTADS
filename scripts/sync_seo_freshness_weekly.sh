#!/usr/bin/env bash
# SEO content freshness weekly scan (Phase 4B)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PTT_FRESHNESS_SCAN_ENABLED="${PTT_FRESHNESS_SCAN_ENABLED:-1}"
cd "$ROOT"
echo "==> SEO freshness weekly scan"
"$PYTHON" -c "
from ptt_seo.freshness import scan_all_freshness_customers
import json
out = scan_all_freshness_customers()
print(json.dumps(out, indent=2, default=str))
if not out.get('ok', True) and not out.get('skipped'):
    raise SystemExit(1)
"
