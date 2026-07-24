#!/usr/bin/env bash
# Meta Enterprise — remote deploy on VPS via SSH
#
# Usage (from laptop, after push to main):
#   PTT_VPS_HOST=rs.pttads.vn APPLY=1 ./scripts/wave_meta_enterprise_deploy_vps.sh
#
# Dry-run on VPS:
#   PTT_VPS_HOST=rs.pttads.vn APPLY=0 ./scripts/wave_meta_enterprise_deploy_vps.sh
#
# Env: PTT_VPS_HOST, PTT_VPS_USER (default deploy), PTT_VPS_ROOT (default /var/www/ptt)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-rs.pttads.vn}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-1}"

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}")

echo "==> Meta Enterprise VPS deploy → ${VPS_USER}@${VPS_HOST}:${VPS_ROOT} (APPLY=$APPLY)"

"${SSH[@]}" bash -s -- "$VPS_ROOT" "$APPLY" <<'EOS'
set -euo pipefail
VPS_ROOT="$1"
APPLY="$2"
cd "$VPS_ROOT"

if [[ ! -f "$VPS_ROOT/scripts/wave_meta_enterprise_deploy.sh" ]]; then
  echo "==> script missing — git pull first"
  git pull --ff-only origin main || git pull --ff-only
fi

export META_DEPLOY_APPLY="$APPLY"
export GIT_PULL=1
export META_APPLY_DDL=1
bash "$VPS_ROOT/scripts/wave_meta_enterprise_deploy.sh"
EOS

echo ""
echo "Done. If smoke skipped credentials, on VPS run:"
echo "  STAFF_PASSWORD='...' ./scripts/wave_meta_enterprise_smoke.sh"
