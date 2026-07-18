#!/usr/bin/env bash
# Reconcile SQLite vs PG crm_leads read replica
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
SAMPLE="${1:-50}"
cd "$ROOT"
echo "==> Reconcile lead replica sample=$SAMPLE"
"$PYTHON" -c "
from ptt_crm.lead_sync import reconcile_leads
import json, sys
report = reconcile_leads(sample_size=int('$SAMPLE'))
print(json.dumps(report, indent=2, ensure_ascii=False))
sys.exit(0 if report.get('ok') else 1)
"
