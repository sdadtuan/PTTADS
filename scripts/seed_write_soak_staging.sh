#!/usr/bin/env bash
# Seed 48h write soak JSONL for staging gate validation (NOT prod sign-off alone)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_WRITE_SOAK_LOG="${PTT_WRITE_SOAK_LOG:-$ROOT/.local-dev/write-soak-evidence.jsonl}"
SAMPLES="${SOAK_SAMPLES:-25}"
SPAN="${SOAK_SPAN_HOURS:-48}"
cd "$ROOT"
echo "==> Seed write soak evidence (staging validation)"
echo "    log=$PTT_WRITE_SOAK_LOG samples=$SAMPLES span=${SPAN}h"
echo "    WARNING: replace with ptt-write-soak.timer for production sign-off"
"$PYTHON" -c "
from ptt_crm.write_soak_evidence import seed_soak_records_for_staging
import json, os
out = seed_soak_records_for_staging(
    sample_count=int(os.environ.get('SOAK_SAMPLES', '25')),
    span_hours=float(os.environ.get('SOAK_SPAN_HOURS', '48')),
)
print(json.dumps(out, indent=2))
raise SystemExit(0 if out.get('ok') else 1)
"
