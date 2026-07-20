#!/usr/bin/env bash
# Deploy SEO Gate D timer lên staging VPS (SSH)
#
# Usage:
#   PTT_VPS_HOST=staging.pttads.vn APPLY=0 ./scripts/staging_seo_gate_d_deploy.sh   # dry-run
#   PTT_VPS_HOST=staging.pttads.vn APPLY=1 ./scripts/staging_seo_gate_d_deploy.sh   # install + smoke
#
# Env:
#   PTT_VPS_HOST      SSH host (default: staging.pttads.vn)
#   PTT_VPS_USER      SSH user (default: deploy)
#   PTT_VPS_ROOT      Repo path (default: /var/www/ptt)
#   APPLY             1 = enable timer + run one-shot smoke (default: 0)
#   GIT_PULL          1 = git pull --ff-only trước deploy (default: 1)
#   LOCAL_SYNC        1 = rsync Gate D files từ máy local (khi chưa push git)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-staging.pttads.vn}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-0}"
GIT_PULL="${GIT_PULL:-1}"
LOCAL_SYNC="${LOCAL_SYNC:-0}"

usage() {
  cat <<EOF
Deploy Gate D systemd timer to staging.

  PTT_VPS_HOST=staging.pttads.vn APPLY=0 $0
  PTT_VPS_HOST=staging.pttads.vn APPLY=1 $0

Docs: docs/runbooks/seo-aeo-gate-d.md
EOF
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}")

if [[ "$LOCAL_SYNC" == "1" ]]; then
  echo "==> LOCAL_SYNC: rsync Gate D artifacts → staging"
  RSYNC=(rsync -avz --relative -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new")
  (
    cd "$ROOT"
    "${RSYNC[@]}" \
      ./deploy/ptt-seo-gate-d.service \
      ./deploy/ptt-seo-gate-d.timer \
      ./deploy/env.staging-seo-gate-d.example \
      ./deploy/sql/seo_aeo_gate_d.sql \
      ./scripts/seo_aeo_cron_gate_d.sh \
      ./scripts/install_seo_gate_d_systemd.sh \
      ./scripts/apply_seo_gate_d_schema.sh \
      ./ptt_seo/gate_d_schema.py \
      ./ptt_seo/cwv.py \
      ./ptt_seo/crawl_reminder.py \
      ./ptt_seo/aeo_schedule.py \
      ./ptt_seo/cron.py \
      ./ptt_seo/alert_notify.py \
      ./ptt_seo/teams_notify.py \
      ./ptt_seo/bi_clickhouse.py \
      ./ptt_seo/automation.py \
      ./ptt_seo/slack_notify.py \
      ./ptt_seo/technical.py \
      "${VPS_USER}@${VPS_HOST}:${VPS_ROOT}/"
  )
  GIT_PULL=0
fi

echo "==> Gate D staging deploy → ${VPS_USER}@${VPS_HOST}:${VPS_ROOT} (APPLY=$APPLY)"

REMOTE_SCRIPT=$(cat <<'EOS'
set -euo pipefail
VPS_ROOT="$1"
APPLY="$2"
GIT_PULL="$3"
cd "$VPS_ROOT"

echo "==> Preflight"
test -d "$VPS_ROOT/.git" || { echo "FAIL: not a git repo: $VPS_ROOT"; exit 1; }
test -f "$VPS_ROOT/scripts/install_seo_gate_d_systemd.sh" || {
  echo "FAIL: Gate D scripts chưa có trên VPS — git pull / deploy code trước"
  exit 1
}

if [[ "$GIT_PULL" == "1" ]]; then
  echo "==> git pull --ff-only"
  git pull --ff-only || git pull --ff-only origin HEAD
fi

echo "==> Merge staging Gate D env (idempotent)"
ENV_EX="$VPS_ROOT/deploy/env.staging-seo-gate-d.example"
ENV_FILE="$VPS_ROOT/.env"
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

echo "==> Apply Gate D DDL"
./scripts/apply_seo_gate_d_schema.sh

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN OK — chạy APPLY=1 để:"
  echo "  sudo ./scripts/install_seo_gate_d_systemd.sh"
  echo "  sudo systemctl enable --now ptt-seo-gate-d.timer"
  echo "  sudo systemctl start ptt-seo-gate-d.service"
  exit 0
fi

echo "==> Install systemd units"
sudo ./scripts/install_seo_gate_d_systemd.sh

echo "==> Enable timer + smoke run"
sudo systemctl enable --now ptt-seo-gate-d.timer
sudo systemctl start ptt-seo-gate-d.service

echo "==> Timer status"
systemctl list-timers --no-pager 'ptt-seo-gate-d*' || true
echo "==> Last run log"
sudo journalctl -u ptt-seo-gate-d.service -n 30 --no-pager || true
EOS
)

if [[ "$APPLY" == "1" ]]; then
  "${SSH[@]}" "bash -s" "$VPS_ROOT" "$APPLY" "$GIT_PULL" <<< "$REMOTE_SCRIPT"
else
  # Dry-run: skip sudo steps — validate SSH + repo + schema only
  "${SSH[@]}" "bash -s" "$VPS_ROOT" "$APPLY" "$GIT_PULL" <<< "$REMOTE_SCRIPT"
fi

echo ""
echo "DONE — Gate D staging deploy (APPLY=$APPLY)"
