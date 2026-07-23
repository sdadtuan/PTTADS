#!/usr/bin/env bash
# Verify Meta Ads retirement dry-run artifact (Horizon 1 B3.5 / M1-G11).
#
# Usage:
#   ./scripts/verify_meta_ads_retirement_dry_run.sh
#   ./scripts/verify_meta_ads_retirement_dry_run.sh run   # regenerate artifact then verify
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

MODE="${1:-verify}"

echo "== Meta Ads retirement dry-run verify (M1-G11) =="

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}"
export HORIZON1_SKIP_SYSTEMD="${HORIZON1_SKIP_SYSTEMD:-1}"
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1
export CRM_FACEBOOK_BACKGROUND=1
export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0

if [[ "$MODE" == "run" ]]; then
  "$PYTHON" -m ptt_crm.meta_ads_retirement_preflight run
else
  "$PYTHON" -m ptt_crm.meta_ads_retirement_preflight verify
fi

export HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN=1
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates >/dev/null

echo ""
echo "M1-G11 retirement dry-run verify PASSED"
echo "Artifact: $PTT_ARTIFACTS_DIR/horizon1-meta-ads-retirement-dry-run.json"
echo "Next: sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh  (B3.6)"
