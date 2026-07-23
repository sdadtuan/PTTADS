#!/usr/bin/env bash
# Verify Meta Ads retirement prod APPLY (Horizon 1 B3.6 / M1-G12).
#
# Usage:
#   ./scripts/verify_meta_ads_retirement_applied.sh verify
#   ./scripts/verify_meta_ads_retirement_applied.sh post
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

MODE="${1:-verify}"

echo "== Meta Ads retirement APPLY verify (M1-G12) mode=$MODE =="

export PTT_FLASK_META_ADS_ADMIN_RETIRED="${PTT_FLASK_META_ADS_ADMIN_RETIRED:-1}"
export HORIZON1_EXPECT_META_HUB_RETIRED="${HORIZON1_EXPECT_META_HUB_RETIRED:-1}"
export HORIZON1_META_RETIREMENT_APPLIED="${HORIZON1_META_RETIREMENT_APPLIED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_WEBHOOKS_FLASK_FALLBACK="${PTT_WEBHOOKS_FLASK_FALLBACK:-0}"
export CRM_FACEBOOK_BACKGROUND=1
export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0
export HORIZON1_SKIP_SOAK=1
export HORIZON1_SKIP_NEST_SMOKE=1

case "$MODE" in
  verify)
    "$PYTHON" -m ptt_crm.meta_ads_retirement_apply verify
    ;;
  post)
    "$PYTHON" -m ptt_crm.meta_ads_retirement_apply post
    ;;
  prerequisite)
    "$PYTHON" -m ptt_crm.meta_ads_retirement_apply prerequisite
    ;;
  *)
    echo "Usage: $0 [verify|post|prerequisite]" >&2
    exit 2
    ;;
esac

export HORIZON1_EXPECT_META_RETIREMENT_APPLIED=1
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}"
export HORIZON1_SKIP_SYSTEMD="${HORIZON1_SKIP_SYSTEMD:-1}"
"$PYTHON" -m ptt_crm.horizon1_meta_ads_gates >/dev/null

echo ""
echo "M1-G12 retirement APPLY verify PASSED"
