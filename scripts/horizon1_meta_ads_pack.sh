#!/usr/bin/env bash
# Horizon 1 — Meta / Facebook Ads migration pack (Flask admin off)
#
# Usage:
#   ./scripts/horizon1_meta_ads_pack.sh preflight   # gates only, soak skipped
#   ./scripts/horizon1_meta_ads_pack.sh soak        # record today's soak snapshot
#   ./scripts/horizon1_meta_ads_pack.sh evaluate    # evaluate soak + merge signoffs
#   ./scripts/horizon1_meta_ads_pack.sh full        # preflight + bootstrap soak + evaluate (staging only)
#   ./scripts/horizon1_meta_ads_pack.sh execute-local # M1-A..F staging automation (local/CI)
#   ./scripts/horizon1_meta_ads_pack.sh metrics     # M1-E pilot metrics
#   ./scripts/horizon1_meta_ads_pack.sh meta-retire # partial Flask Meta hub retire (dry-run / APPLY=1)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

ENV_EXAMPLE="$ROOT/deploy/env.horizon1-meta-ads.example"
if [[ -f "$ENV_EXAMPLE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  set +a
fi

MODE="${1:-preflight}"

case "$MODE" in
  preflight)
    export HORIZON1_SKIP_SOAK=1
    echo "==> Horizon 1 Meta Ads preflight (gates, soak skipped)"
    if [[ -f "$ROOT/ptt.db" ]] && [[ -n "${DATABASE_URL:-}" ]]; then
      "$PYTHON" "$ROOT/scripts/seed_staff_meta_permissions.py" || true
    else
      "$PYTHON" "$ROOT/scripts/seed_staff_meta_permissions.py" --dry-run || true
    fi
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_gates
    ;;
  soak)
    export HORIZON1_SKIP_SOAK=0
    echo "==> Record Meta soak snapshot"
    "$ROOT/scripts/horizon1_meta_ads_soak_record.sh"
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff merge || true
    ;;
  evaluate)
    export HORIZON1_SKIP_SOAK=0
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff merge
    ;;
  full)
    export HORIZON1_BOOTSTRAP_SOAK=1
    export HORIZON1_SKIP_SOAK=1
    echo "==> Horizon 1 full (staging bootstrap soak — NOT for prod)"
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_gates
    export HORIZON1_SKIP_SOAK=0
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff bootstrap
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff merge
    ;;
  execute-local)
    echo "==> Horizon 1 execute-local (M1-A..F staging — NOT prod)"
    export HORIZON1_SKIP_SOAK=1
    export HORIZON1_SKIP_NEST_SMOKE=1
    export HORIZON1_BOOTSTRAP_SOAK=1
    export HORIZON1_STAGING_SIGNOFF=1
    export HORIZON1_MARK_MANUAL_UAT=1
    export PTT_WEBHOOKS_NEST_META=1
    export PTT_WEBHOOKS_FLASK_FALLBACK=0
    export CRM_FACEBOOK_BACKGROUND=1
    export CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0
    export PTT_FLASK_META_ADS_ADMIN_RETIRED=1
    export HORIZON1_EXPECT_META_HUB_RETIRED=1
    echo "M1-A prerequisites + preflight"
    "$PYTHON" "$ROOT/scripts/seed_staff_meta_permissions.py" --dry-run
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_gates
    echo "M1-B1/B2/B3 flags applied (env)"
    echo "M1-C soak bootstrap"
    export HORIZON1_SKIP_SOAK=0
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff bootstrap
    echo "M1-D dry-run meta retire gates"
    chmod +x "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
    APPLY=0 "$ROOT/scripts/close_flask_retirement_meta_ads.sh" || true
    echo "M1-E metrics"
    if [[ -n "${DATABASE_URL:-}" ]]; then
      "$ROOT/scripts/generate_horizon1_meta_metrics.sh" "${HORIZON1_METRICS_DAYS:-28}" || true
    else
      echo "SKIP metrics — DATABASE_URL not set"
    fi
    echo "M1-F finalize signoff"
    "$PYTHON" -m ptt_crm.horizon1_meta_ads_signoff finalize
    ;;
  metrics)
    chmod +x "$ROOT/scripts/generate_horizon1_meta_metrics.sh"
    "$ROOT/scripts/generate_horizon1_meta_metrics.sh" "${2:-${HORIZON1_METRICS_DAYS:-28}}"
    ;;
  meta-retire)
    chmod +x "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
    sudo -E "$ROOT/scripts/close_flask_retirement_meta_ads.sh"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

RC=$?
echo ""
if [[ -f "$PTT_ARTIFACTS_DIR/horizon1-meta-ads-signoff.json" ]]; then
  echo "Sign-off artifact: $PTT_ARTIFACTS_DIR/horizon1-meta-ads-signoff.json"
fi
exit "$RC"
