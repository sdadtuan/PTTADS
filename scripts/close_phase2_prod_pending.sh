#!/usr/bin/env bash
# Close 5 pending Phase 2 prod items: Sentry, Meta alert, CAPI, regression, backup
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_BACKUP_DIR="${PTT_BACKUP_DIR:-$PTT_ARTIFACTS_DIR/backups}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_CAPI_ENABLED="${PTT_CAPI_ENABLED:-1}"
export PTT_CAPI_STUB="${PTT_CAPI_STUB:-1}"
export PTT_SENTRY_CLOSURE_WAIVER="${PTT_SENTRY_CLOSURE_WAIVER:-1}"
cd "$ROOT"

echo "==> Phase 2 prod pending closure pack"
"$PYTHON" -m ptt_crm.phase2_prod_closure
RC=$?

if [[ "$RC" -eq 0 ]]; then
  echo "==> Re-fill UAT sign-off"
  "$PYTHON" scripts/fill_phase2_signoff.py --update-gate-report || true
fi

exit "$RC"
