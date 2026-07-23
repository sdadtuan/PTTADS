#!/usr/bin/env bash
# Wave B5 S0 — remote deploy on VPS via SSH (rs.pttads.vn / staging)
#
# Usage:
#   PTT_VPS_HOST=rs.pttads.vn APPLY=1 ./scripts/wave_b5_s0_deploy_vps.sh
#   LOCAL_SYNC=1 PTT_VPS_HOST=rs.pttads.vn APPLY=1 ./scripts/wave_b5_s0_deploy_vps.sh  # chưa push git
#
# Env:
#   PTT_VPS_HOST     SSH host (default: rs.pttads.vn)
#   PTT_VPS_USER     SSH user (default: deploy)
#   PTT_VPS_ROOT     Repo path (default: /var/www/ptt)
#   APPLY            1 = merge env + deploy + restart (default: 0 dry-run preflight)
#   GIT_PULL         1 = git pull before deploy (default: 1)
#   LOCAL_SYNC       1 = rsync Wave B5 S0 files from local (default: 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-rs.pttads.vn}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-0}"
GIT_PULL="${GIT_PULL:-1}"
LOCAL_SYNC="${LOCAL_SYNC:-0}"

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}")

if [[ "$LOCAL_SYNC" == "1" ]]; then
  echo "==> LOCAL_SYNC: rsync Wave B5 S0 → ${VPS_USER}@${VPS_HOST}:${VPS_ROOT}"
  RSYNC=(rsync -avz --relative -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new")
  (
    cd "$ROOT"
    "${RSYNC[@]}" \
      ./deploy/env.crm-flask-migration.example \
      ./docs/runbooks/wave-b5-dev-plan.md \
      ./docs/specs/2026-07-23-wave-b5-s0-promote-bridge-design.md \
      ./scripts/wave_b5_s0_deploy.sh \
      ./scripts/wave_b5_s0_deploy_vps.sh \
      ./scripts/wave_b5_s0_gate.sh \
      ./scripts/wave_b5_s0_smoke.sh \
      ./services/ptt-crm-api/src/leads-contract/ \
      ./services/ptt-crm-api/src/app.module.ts \
      ./services/ptt-crm-api/src/config/app-config.service.ts \
      ./services/ops-web/src/components/LeadContractPanel.tsx \
      ./services/ops-web/src/components/ContractApprovalsPanel.tsx \
      ./services/ops-web/src/app/crm/hub/CrmHubContent.tsx \
      ./services/ops-web/src/app/crm/leads/\[id\]/page.tsx \
      ./services/ops-web/src/app/agency/clients/\[id\]/AgencyClientDetailContent.tsx \
      ./services/ops-web/src/lib/api.ts \
      "${VPS_USER}@${VPS_HOST}:${VPS_ROOT}/"
  )
  GIT_PULL=0
fi

echo "==> Wave B5 S0 VPS deploy → ${VPS_USER}@${VPS_HOST}:${VPS_ROOT} (APPLY=$APPLY)"

"${SSH[@]}" bash -s -- "$VPS_ROOT" "$APPLY" "$GIT_PULL" <<'EOS'
set -euo pipefail
VPS_ROOT="$1"
APPLY="$2"
GIT_PULL="$3"
cd "$VPS_ROOT"

echo "==> Preflight"
test -d "$VPS_ROOT/.git" || { echo "FAIL: not a git repo: $VPS_ROOT"; exit 1; }
test -f "$VPS_ROOT/scripts/wave_b5_s0_deploy.sh" || {
  echo "FAIL: wave_b5_s0_deploy.sh chưa có — git pull hoặc LOCAL_SYNC=1 trước"
  exit 1
}

if [[ "$GIT_PULL" == "1" ]]; then
  echo "==> git pull --ff-only"
  git pull --ff-only || git pull --ff-only origin HEAD
fi

if [[ "$APPLY" != "1" ]]; then
  echo "DRY-RUN OK — chạy APPLY=1 để deploy thật"
  exit 0
fi

export WAVE_B5_S0_UPDATE_ENV=1
export NEXT_PUBLIC_PTT_API_URL="https://${PTT_VPS_HOST:-rs.pttads.vn}"
bash "$VPS_ROOT/scripts/wave_b5_s0_deploy.sh"

echo ""
echo "==> Smoke (localhost Nest)"
if [[ -n "${ADMIN_PASSWORD:-}" ]]; then
  ADMIN_PASSWORD="$ADMIN_PASSWORD" bash "$VPS_ROOT/scripts/wave_b5_s0_smoke.sh"
else
  echo "SKIP smoke — set ADMIN_PASSWORD on VPS shell rồi chạy ./scripts/wave_b5_s0_smoke.sh"
fi
EOS

echo ""
echo "UAT manual:"
echo "  1. AM: /crm/leads/<id> → HĐ draft → Gửi GDKD duyệt"
echo "  2. GDKD: /crm/hub → tab HĐ chờ duyệt → Duyệt"
echo "  3. Verify: /crm/service-delivery lifecycle Onboard"
