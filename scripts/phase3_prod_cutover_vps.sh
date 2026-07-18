#!/usr/bin/env bash
# Run Phase 3 prod cutover on VPS via SSH (or print local dry-run commands)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-0}"

usage() {
  cat <<EOF
Usage: PTT_VPS_HOST=vps.example.com [APPLY=1] $0

Env:
  PTT_VPS_HOST     SSH host (required for remote run)
  PTT_VPS_USER     SSH user (default: deploy)
  PTT_VPS_ROOT     Repo on VPS (default: /var/www/ptt)
  APPLY            1 = apply systemd+certbot on VPS (default: 0 dry-run)
  PORTAL_PILOT_PASSWORD  required for seed_portal_pilot_users.py

Local dry-run (no SSH):
  cd $ROOT && APPLY=0 ./scripts/close_phase3_prod_cutover.sh

Remote dry-run:
  PTT_VPS_HOST=your.vps APPLY=0 $0

Remote apply:
  PTT_VPS_HOST=your.vps APPLY=1 PORTAL_PILOT_PASSWORD='...' $0
EOF
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$VPS_HOST" ]]; then
  echo "==> No PTT_VPS_HOST — running local VPS cutover dry-run"
  cd "$ROOT"
  export PTT_CUTOVER_SKIP_URL_CHECK=1
  export PTT_CUTOVER_SKIP_SYSTEMD=1
  export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
  export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
  export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars-for-local-dry-run}"
  export PORTAL_PILOT_PASSWORD="${PORTAL_PILOT_PASSWORD:-local-dry-run-pilot-password}"
  export PTT_PILOT_SEED_ALLOW_PLAIN="${PTT_PILOT_SEED_ALLOW_PLAIN:-1}"
  APPLY="$APPLY" ./scripts/close_phase3_prod_cutover.sh
  exit $?
fi

: "${PORTAL_PILOT_PASSWORD:?Set PORTAL_PILOT_PASSWORD for remote cutover}"

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}")

echo "==> Remote preflight on ${VPS_USER}@${VPS_HOST}:${VPS_ROOT}"
"${SSH[@]}" "cd '${VPS_ROOT}' && export APPLY='${APPLY}' PORTAL_PILOT_PASSWORD='${PORTAL_PILOT_PASSWORD}' PTT_CUTOVER_SKIP_URL_CHECK=0 && ./scripts/close_phase3_prod_cutover.sh"

if [[ "$APPLY" == "1" ]]; then
  echo ""
  echo "==> Post-cutover Playwright (from local machine against prod URLs)"
  echo "PORTAL_E2E_URL=https://portal.pttads.vn \\"
  echo "PORTAL_E2E_API_URL=https://portal.pttads.vn \\"
  echo "PORTAL_E2E_APPROVER_EMAIL=approver.pilot1@pttads.vn \\"
  echo "PORTAL_E2E_APPROVER_PASSWORD='<pilot-password>' \\"
  echo "  ./scripts/phase3_playwright_e2e_gate.sh"
fi
