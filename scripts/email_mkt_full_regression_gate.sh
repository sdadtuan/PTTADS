#!/usr/bin/env bash
# Full email marketing regression — EM-0..EM-4 + Waves 1–3b + Wave 4 prod pilot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export EM5_INCLUDE_WAVE_GATES=1
export EM5_SKIP_SOAK="${EM5_SKIP_SOAK:-1}"
export SKIP_CLICKHOUSE="${SKIP_CLICKHOUSE:-1}"
export SKIP_NEST_SMOKE="${SKIP_NEST_SMOKE:-0}"

echo "==> EM-0..EM-4 foundation gates"
bash "$ROOT/scripts/phase0_email_hub_kickoff_gate.sh"
bash "$ROOT/scripts/phase1_email_ops_gate.sh"
bash "$ROOT/scripts/phase2_email_send_mvp_gate.sh"
bash "$ROOT/scripts/phase3_email_enterprise_gate.sh"
bash "$ROOT/scripts/phase4_email_portal_gate.sh"

echo ""
echo "==> Wave 1 — EM-6 Send Platform"
bash "$ROOT/scripts/phase6_email_send_platform_gate.sh"

echo ""
echo "==> Wave 2 — EM-7 measurement"
bash "$ROOT/scripts/phase7_email_wave2_gate.sh"

echo ""
echo "==> Wave 3 — EM-8 UX"
bash "$ROOT/scripts/phase8_email_wave3_gate.sh"

echo ""
echo "==> Wave 3b — EM-8b UX polish"
bash "$ROOT/scripts/phase8b_email_wave3b_gate.sh"

echo ""
echo "==> Wave 4 — EM-9 prod pilot pack"
bash "$ROOT/scripts/phase9_email_wave4_gate.sh"

echo ""
echo "OK  email_mkt_full_regression_gate — all gates passed"
