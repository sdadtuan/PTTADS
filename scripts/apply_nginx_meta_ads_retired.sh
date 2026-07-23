#!/usr/bin/env bash
# Apply nginx redirect: /crm/facebook-ads → ops.pttads.vn/meta/facebook-ads
# Usage: sudo ./scripts/apply_nginx_meta_ads_retired.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNIPPET_SRC="$ROOT/deploy/nginx-meta-ads-retired-snippet.conf"
NGINX_SITE="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"

if [[ ! -f "$SNIPPET_SRC" ]]; then
  echo "Missing $SNIPPET_SRC" >&2
  exit 1
fi

if [[ ! -f "$NGINX_SITE" ]]; then
  echo "WARN nginx site not found: $NGINX_SITE — skip apply (dev/local)" >&2
  exit 0
fi

if grep -q 'location \^~ /crm/facebook-ads' "$NGINX_SITE" 2>/dev/null; then
  echo "OK  nginx already has /crm/facebook-ads redirect"
else
  echo "==> Append Meta redirect snippet to $NGINX_SITE"
  cp -a "$NGINX_SITE" "${NGINX_SITE}.pre-meta-ads-retired.bak"
  {
    echo ""
    echo "# Horizon 1 B3.3 — Meta Ads Flask admin retired ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
    cat "$SNIPPET_SRC"
  } >>"$NGINX_SITE"
  echo "OK  appended snippet (backup: ${NGINX_SITE}.pre-meta-ads-retired.bak)"
fi

if command -v nginx >/dev/null 2>&1; then
  nginx -t
  systemctl reload nginx
  echo "OK  nginx reloaded"
fi
