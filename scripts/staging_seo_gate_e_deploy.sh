#!/usr/bin/env bash
# Apply Gate E schema + CMS auto-publish pilot env on staging VPS (SSH)
#
# Usage:
#   PTT_VPS_HOST=<staging-ip> APPLY=0 ./scripts/staging_seo_gate_e_deploy.sh
#   PTT_VPS_HOST=<staging-ip> APPLY=1 PILOT_CUSTOMER_ID=1 ./scripts/staging_seo_gate_e_deploy.sh
#
# Env:
#   PTT_VPS_HOST           SSH host (default: staging.pttads.vn)
#   PTT_VPS_USER           SSH user (default: deploy)
#   PTT_VPS_ROOT           Repo path (default: /var/www/ptt)
#   APPLY                  1 = restart ptt + seed CMS pilot (default: 0)
#   GIT_PULL               1 = git pull before deploy (default: 1)
#   LOCAL_SYNC             1 = rsync Gate E files from local (default: 0)
#   PILOT_CUSTOMER_ID      CRM customer id for seed_cms_webhook_pilot.py (optional)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-staging.pttads.vn}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-0}"
GIT_PULL="${GIT_PULL:-1}"
LOCAL_SYNC="${LOCAL_SYNC:-0}"
PILOT_CUSTOMER_ID="${PILOT_CUSTOMER_ID:-}"

usage() {
  cat <<EOF
Apply Gate E schema + PTT_SEO_CMS_AUTO_PUBLISH on staging.

  PTT_VPS_HOST=<host> APPLY=0 $0
  PTT_VPS_HOST=<host> APPLY=1 PILOT_CUSTOMER_ID=1 $0
  LOCAL_SYNC=1 PTT_VPS_HOST=<host> APPLY=1 $0   # code chưa push git

Docs: docs/runbooks/seo-aeo-gate-e.md
EOF
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}")

if [[ "$LOCAL_SYNC" == "1" ]]; then
  echo "==> LOCAL_SYNC: rsync Gate E artifacts → staging"
  RSYNC=(rsync -avz --relative -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new")
  (
    cd "$ROOT"
    "${RSYNC[@]}" \
      ./deploy/env.staging-seo-gate-e.example \
      ./deploy/sql/seo_aeo_gate_e.sql \
      ./scripts/apply_seo_gate_e_schema.sh \
      ./scripts/staging_seo_gate_e_deploy.sh \
      ./scripts/seed_cms_webhook_pilot.py \
      ./ptt_seo/gate_e_schema.py \
      ./ptt_seo/strategy_okr.py \
      ./ptt_seo/crawl_connector.py \
      ./ptt_seo/entity_autolink.py \
      ./ptt_seo/rank_live.py \
      ./ptt_seo/attribution.py \
      ./ptt_seo/cms_publish.py \
      ./ptt_seo/content.py \
      ./ptt_seo/cwv.py \
      ./ptt_seo/cron.py \
      ./ptt_seo/db.py \
      ./ptt_seo/schema.py \
      ./ptt_seo/bi_clickhouse.py \
      ./ptt_seo/connectors/ga4_sync.py \
      ./blueprints/seo_aeo.py \
      "${VPS_USER}@${VPS_HOST}:${VPS_ROOT}/"
  )
  GIT_PULL=0
fi

echo "==> Gate E staging deploy → ${VPS_USER}@${VPS_HOST}:${VPS_ROOT} (APPLY=$APPLY)"

REMOTE_SCRIPT=$(cat <<'EOS'
set -euo pipefail
VPS_ROOT="$1"
APPLY="$2"
GIT_PULL="$3"
PILOT_CID="$4"
cd "$VPS_ROOT"

PYTHON="${PYTHON:-python3}"
if [[ -x "$VPS_ROOT/.venv/bin/python" ]]; then
  PYTHON="$VPS_ROOT/.venv/bin/python"
fi

echo "==> Preflight"
test -d "$VPS_ROOT/.git" || { echo "FAIL: not a git repo: $VPS_ROOT"; exit 1; }
test -f "$VPS_ROOT/scripts/apply_seo_gate_e_schema.sh" || {
  echo "FAIL: Gate E scripts chưa có trên VPS — git pull / LOCAL_SYNC=1 trước"
  exit 1
}

if [[ "$GIT_PULL" == "1" ]]; then
  echo "==> git pull --ff-only"
  git pull --ff-only || git pull --ff-only origin HEAD
fi

ENV_EX="$VPS_ROOT/deploy/env.staging-seo-gate-e.example"
ENV_FILE="$VPS_ROOT/.env"

echo "==> Merge staging Gate E env (idempotent append)"
if [[ -f "$ENV_EX" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    if ! grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
      echo "$line" >> "$ENV_FILE"
      echo "  + $key"
    fi
  done < "$ENV_EX"
fi

echo "==> Force-enable CMS auto-publish pilot flags"
for kv in \
  "PTT_SEO_CMS_AUTO_PUBLISH=1" \
  "PTT_SEO_ENTERPRISE_ENABLED=1" \
  "PTT_CRAWL_CONNECTOR_ENABLED=1" \
  "PTT_RANK_LIVE_ENABLED=1"; do
  key="${kv%%=*}"
  val="${kv#*=}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i.bak "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    echo "  ~ $key"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
    echo "  + $key"
  fi
done

echo "==> Apply Gate E DDL"
./scripts/apply_seo_gate_e_schema.sh

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN OK — chạy APPLY=1 để:"
  echo "  sudo systemctl restart ptt"
  echo "  python3 scripts/seed_cms_webhook_pilot.py --customer-id <id>"
  exit 0
fi

if [[ -n "$PILOT_CID" ]]; then
  echo "==> Seed CMS webhook pilot for customer $PILOT_CID"
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
  export PYTHONPATH="$VPS_ROOT${PYTHONPATH:+:$PYTHONPATH}"
  "$PYTHON" "$VPS_ROOT/scripts/seed_cms_webhook_pilot.py" --customer-id "$PILOT_CID"
fi

echo "==> Restart Flask (ptt) to load .env"
sudo systemctl restart ptt
sleep 2
systemctl is-active ptt || { echo "WARN: ptt service not active"; exit 1; }

echo "==> Verify CMS auto-publish env loaded"
grep -E '^PTT_SEO_CMS_AUTO_PUBLISH=|^PTT_SEO_ENTERPRISE_ENABLED=' "$ENV_FILE" || true
EOS
)

"${SSH[@]}" "bash -s" "$VPS_ROOT" "$APPLY" "$GIT_PULL" "$PILOT_CUSTOMER_ID" <<< "$REMOTE_SCRIPT"

echo ""
echo "DONE — Gate E staging deploy (APPLY=$APPLY)"
