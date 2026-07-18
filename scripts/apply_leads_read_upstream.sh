#!/usr/bin/env bash
# Apply PTT_LEADS_READ_UPSTREAM to Nginx snippet (Phase 1b Bước 8)
#
# Local (dry-run):
#   ./scripts/apply_leads_read_upstream.sh --dry-run
#
# VPS:
#   sudo ./scripts/apply_leads_read_upstream.sh
#   sudo ./scripts/apply_leads_read_upstream.sh --reload
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
SNIPPET_DEST="${NGINX_SNIPPET:-/etc/nginx/snippets/ptt-leads-v1-routing.conf}"
DRY_RUN=0
RELOAD=0

usage() {
  cat <<'EOF'
Usage: apply_leads_read_upstream.sh [--dry-run] [--reload] [--dest PATH]

Reads PTT_LEADS_READ_UPSTREAM from .env (default: flask).
Copies deploy/nginx-leads-v1-upstream-{nest,flask}.conf to Nginx snippet.

Env:
  PTT_LEADS_READ_UPSTREAM   flask | nest
  NGINX_SNIPPET             output path (default /etc/nginx/snippets/...)
  ENV_FILE                  .env path
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --reload) RELOAD=1 ;;
    --dest) SNIPPET_DEST="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

MODE="flask"
if [[ -f "$ENV_FILE" ]]; then
  val="$(grep -E '^PTT_LEADS_READ_UPSTREAM=' "$ENV_FILE" | tail -1 | cut -d= -f2- | sed 's/^[[:space:]"'\'' ]*//; s/[[:space:]"'\'' ]*$//' || true)"
  if [[ -n "${val:-}" ]]; then
    MODE="$(echo "$val" | tr '[:upper:]' '[:lower:]')"
  fi
fi
MODE="${PTT_LEADS_READ_UPSTREAM:-$MODE}"
MODE="$(echo "$MODE" | tr '[:upper:]' '[:lower:]')"

case "$MODE" in
  nest|flask) ;;
  *)
    echo "FAIL invalid PTT_LEADS_READ_UPSTREAM=$MODE (use nest or flask)" >&2
    exit 1
    ;;
esac

SRC="$ROOT/deploy/nginx-leads-v1-upstream-${MODE}.conf"
if [[ ! -f "$SRC" ]]; then
  echo "FAIL missing template $SRC" >&2
  exit 1
fi

echo "==> PTT_LEADS_READ_UPSTREAM=$MODE"
echo "    src:  $SRC"
echo "    dest: $SNIPPET_DEST"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "--- dry-run snippet ---"
  cat "$SRC"
  exit 0
fi

mkdir -p "$(dirname "$SNIPPET_DEST")"
cp "$SRC" "$SNIPPET_DEST"
echo "OK  wrote $SNIPPET_DEST"

if [[ "$RELOAD" -eq 1 ]]; then
  if command -v nginx >/dev/null 2>&1; then
    nginx -t
    if command -v systemctl >/dev/null 2>&1; then
      systemctl reload nginx
    else
      nginx -s reload
    fi
    echo "OK  nginx reloaded"
  else
    echo "WARN nginx not found — reload manually after deploy"
  fi
fi

# Remind: restart Flask if using app-level proxy on pttads.vn
echo ""
echo "Next:"
echo "  1. Ensure ptt-crm-api on :3000 (systemd or docker compose)"
echo "  2. Set PTT_LEADS_READ_UPSTREAM=$MODE in .env + restart ptt.service if Flask app proxy"
echo "  3. Verify: ./scripts/local_leads_cutover_drill.sh"
