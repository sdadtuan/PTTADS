#!/usr/bin/env bash
# Record daily Phase 5 health snapshot (cron / systemd timer on prod)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export SEO_AEO_DB="${SEO_AEO_DB:-pg}"
export PTT_PHASE5_SOAK_LOG="${PTT_PHASE5_SOAK_LOG:-$ROOT/.local-dev/phase5-soak-evidence.jsonl}"
cd "$ROOT"
echo "==> Phase 5 soak record"
"$PYTHON" -m ptt_crm.phase5_soak_evidence record
