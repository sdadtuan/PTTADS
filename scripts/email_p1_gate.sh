#!/usr/bin/env bash
# Email Marketing P1 UX parity gate — domain QA + handoff regression (no Flask)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
python3 -m ptt_crm.email_p1_gates
