#!/usr/bin/env bash
# Meta Enterprise — post-deploy smoke (Phase 0 gate + B8/B9 API smoke)
#
# Usage (on VPS, Nest listening on :3000):
#   cd /var/www/ptt && ./scripts/wave_meta_enterprise_smoke.sh
#
# Env:
#   BASE                 API base (default: http://127.0.0.1:3000)
#   STAFF_EMAIL          staff login (default: staff@demo.local)
#   STAFF_PASSWORD       staff password
#   PORTAL_EMAIL         portal login (default: approver@demo.local)
#   PORTAL_PASSWORD      portal password
#   META_SMOKE_SKIP_P0   1 = skip phase0 gate
#   META_SMOKE_SKIP_B8   1 = skip wave_b8_smoke.sh
#   META_SMOKE_SKIP_B9   1 = skip wave_b9_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export BASE="${BASE:-http://127.0.0.1:3000}"
export STAFF_EMAIL="${STAFF_EMAIL:-staff@demo.local}"
export STAFF_PASSWORD="${STAFF_PASSWORD:-${ADMIN_PASSWORD:-demo123}}"
export PORTAL_EMAIL="${PORTAL_EMAIL:-approver@demo.local}"
export PORTAL_PASSWORD="${PORTAL_PASSWORD:-${ADMIN_PASSWORD:-demo123}}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

fail=0

echo "== Meta Enterprise smoke =="
echo "BASE=$BASE"
echo "STAFF_EMAIL=$STAFF_EMAIL"

if [[ "${META_SMOKE_SKIP_P0:-0}" != "1" ]]; then
  echo ""
  echo "-- Phase 0 gate (static + unit, skip build) --"
  WAVE_META_P0_SKIP_BUILD=1 bash "$ROOT/scripts/wave_meta_phase0_gate.sh"
else
  echo "SKIP Phase 0 gate"
fi

if [[ "${META_SMOKE_SKIP_B8:-0}" != "1" ]]; then
  echo ""
  bash "$ROOT/scripts/wave_b8_smoke.sh" || fail=1
else
  echo "SKIP B8 smoke"
fi

if [[ "${META_SMOKE_SKIP_B9:-0}" != "1" ]]; then
  echo ""
  if [[ "${PTT_META_TRACKING_ENABLED:-0}" == "1" ]]; then
    bash "$ROOT/scripts/wave_b9_smoke.sh" || fail=1
  else
    echo "SKIP B9 smoke — PTT_META_TRACKING_ENABLED=0 (enable after pilot env merge)"
  fi
else
  echo "SKIP B9 smoke"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Meta Enterprise smoke PASSED"
  exit 0
fi
echo "Meta Enterprise smoke FAILED"
exit 1
