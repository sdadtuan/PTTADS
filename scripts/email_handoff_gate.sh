#!/usr/bin/env bash
# Email Marketing §13 handoff gate — ops-web Playwright + domain QA (no Flask)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
python3 -m ptt_crm.email_handoff_gates
