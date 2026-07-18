#!/usr/bin/env bash
# Dual-run Flask vs Nest leads API — requires ptt-crm-api running on :3000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

SAMPLE="${1:-20}"
echo "==> Dual-run check sample=$SAMPLE nest=$PTT_NEST_LEADS_URL sqlite=$PTT_SQLITE_PATH"

if ! curl -sf "$PTT_NEST_LEADS_URL/health" >/dev/null 2>&1; then
  echo "FAIL NestJS not reachable at $PTT_NEST_LEADS_URL — start: ./scripts/local_crm_api_up.sh"
  exit 1
fi

cd "$ROOT"
"$PYTHON" scripts/dual_run_leads_check.py --sample "$SAMPLE" --quiet
echo "OK  dual-run passed"
