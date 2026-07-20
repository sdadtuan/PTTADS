#!/usr/bin/env bash
# EM-5 — record daily email marketing health snapshot (cron on staging/prod)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_EM5_SOAK_LOG="${PTT_EM5_SOAK_LOG:-$ROOT/.local-dev/em5-soak-evidence.jsonl}"
cd "$ROOT"
echo "==> EM-5 email soak record"
"$PYTHON" -m ptt_crm.phase5_email_soak_evidence record
