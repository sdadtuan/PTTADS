#!/usr/bin/env bash
# Phase 4 prod cutover on VPS via SSH (or local dry-run)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VPS_HOST="${PTT_VPS_HOST:-}"
VPS_USER="${PTT_VPS_USER:-deploy}"
VPS_ROOT="${PTT_VPS_ROOT:-/var/www/ptt}"
APPLY="${APPLY:-0}"

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage: PTT_VPS_HOST=vps.example.com [APPLY=1] $0

Local dry-run:
  APPLY=0 ./scripts/phase4_prod_cutover_vps.sh

Remote apply:
  PTT_VPS_HOST=your.vps APPLY=1 \\
    PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=<uuid> \\
    PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<meta_campaign_id> \\
    $0
EOF
  exit 0
fi

if [[ -z "$VPS_HOST" ]]; then
  echo "==> Local Phase 4 cutover dry-run"
  cd "$ROOT"
  export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
  export PTT_CUTOVER_SKIP_PILOT=1
  export PTT_FLASK_MONOLITH_MODE="${PTT_FLASK_MONOLITH_MODE:-readonly}"
  export PTT_META_CAMPAIGN_WRITE_STUB="${PTT_META_CAMPAIGN_WRITE_STUB:-1}"
  APPLY="$APPLY" ./scripts/close_phase4_prod_cutover.sh
  exit $?
fi

: "${PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS:?Set pilot client UUID}"
: "${PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS:?Set Meta campaign ID}"

ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${VPS_USER}@${VPS_HOST}" \
  "cd '${VPS_ROOT}' && export APPLY='${APPLY}' \
    PTT_FLASK_MONOLITH_MODE='${PTT_FLASK_MONOLITH_MODE:-readonly}' \
    PTT_META_CAMPAIGN_WRITE_STUB='${PTT_META_CAMPAIGN_WRITE_STUB:-0}' \
    PTT_META_CAMPAIGN_WRITE_PILOT='${PTT_META_CAMPAIGN_WRITE_PILOT:-1}' \
    PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS='${PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS}' \
    PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS='${PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS}' \
    ./scripts/close_phase4_prod_cutover.sh"
