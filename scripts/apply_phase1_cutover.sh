#!/usr/bin/env bash
# Phase 1 production cutover — PG primary leads, Nest read/write, all webhooks → Nest
#
# Local dry-run:
#   ./scripts/apply_phase1_cutover.sh --dry-run
#
# VPS:
#   sudo ./scripts/apply_phase1_cutover.sh --reload
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=0
RELOAD=0
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage: apply_phase1_cutover.sh [--dry-run] [--reload]

Applies:
  - deploy/nginx-leads-v1-upstream-nest.conf  (PTT_LEADS_READ_UPSTREAM=nest)
  - deploy/nginx-webhooks-v1-upstream-nest-all.conf

Also set env from deploy/env.phase1-prod.example before restart services.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; EXTRA_ARGS+=(--dry-run) ;;
    --reload) RELOAD=1; EXTRA_ARGS+=(--reload) ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

echo "==> Phase 1 cutover: PostgreSQL primary — không ghi lead vào ptt.db"
echo ""

export PTT_LEADS_READ_UPSTREAM=nest
"$ROOT/scripts/apply_leads_read_upstream.sh" "${EXTRA_ARGS[@]}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "--- dry-run webhooks nest-all ---"
  cat "$ROOT/deploy/nginx-webhooks-v1-upstream-nest-all.conf"
else
  SNIPPET_DST="${NGINX_SNIPPET_DST:-/etc/nginx/snippets/ptt-webhooks-v1-routing.conf}"
  echo "==> webhooks nest-all → $SNIPPET_DST"
  sudo cp "$ROOT/deploy/nginx-webhooks-v1-upstream-nest-all.conf" "$SNIPPET_DST"
  if [[ "$RELOAD" -eq 1 ]]; then
    sudo nginx -t
    sudo systemctl reload nginx
    echo "OK  nginx reloaded (webhooks nest-all)"
  fi
fi

echo ""
echo "Env (see deploy/env.phase1-prod.example):"
echo "  PTT_LEADS_WRITE_SOURCE=pg"
echo "  PTT_LEADS_READ_SOURCE=pg"
echo "  PTT_LEAD_REPLICA_SYNC=0"
echo "  PTT_LEADS_WRITE_ENABLED=1"
echo "  PTT_LEADS_READ_UPSTREAM=nest"
echo "  PTT_LEADS_WRITE_UPSTREAM=nest"
echo "  PTT_WEBHOOKS_FLASK_FALLBACK=0"
echo ""
echo "Restart: ptt-crm-api ptt-worker ptt-fb-autosync ptt ops-web"
