#!/usr/bin/env bash
# Patch existing rs.pttads.vn nginx site with /_next/static/ alias (keeps SSL paths intact).
#   sudo ./scripts/patch_nginx_rs_static.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Usage: sudo $0"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/nginx_ssl_paths.sh
. "$ROOT/scripts/lib/nginx_ssl_paths.sh"
DEST="${NGINX_RS_SITE:-/etc/nginx/sites-available/rs.pttads.vn}"
STATIC_ALIAS="${ROOT}/services/ops-web/.next/standalone/.next/static/"

if [[ ! -f "$DEST" ]]; then
  echo "FAIL  nginx site missing: $DEST"
  echo "      Create site first or run certbot, then re-run this script."
  exit 1
fi

if [[ ! -d "$STATIC_ALIAS" ]]; then
  echo "FAIL  ops-web static not built: $STATIC_ALIAS"
  echo "      Run as deploy: export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b1_rebuild_ops_web.sh"
  exit 1
fi

backup="${DEST}.bak.$(date +%Y%m%d%H%M%S)"
cp "$DEST" "$backup"
echo "Backup → $backup"

python3 - "$DEST" "$STATIC_ALIAS" <<'PY'
import sys
from pathlib import Path

dest = Path(sys.argv[1])
static_alias = sys.argv[2].rstrip("/") + "/"
text = dest.read_text()

if "location /_next/static/" in text:
    print("SKIP  /_next/static/ block already present")
    sys.exit(0)

block = f"""    # Next.js static assets — serve from disk (standalone build)
    location /_next/static/ {{
        alias {static_alias};
        access_log off;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }}

"""

markers = (
    "    location / {\n        proxy_pass http://ptt_ops_web",
    "    location / {\n        proxy_pass http://ptt_flask_agency",
    "    location / {",
)
for needle in markers:
    if needle in text:
        dest.write_text(text.replace(needle, block + needle, 1))
        print("OK    inserted /_next/static/ alias before location /")
        sys.exit(0)

print("FAIL  could not find 'location /' block to patch")
sys.exit(1)
PY

cert_line="$(grep -m1 '^\s*ssl_certificate\s' "$DEST" | awk '{print $2}' | tr -d ';' || true)"
if [[ -n "$cert_line" && ! -f "$cert_line" ]]; then
  echo "WARN  SSL path missing ($cert_line) — rewriting to /etc/nginx/ssl/"
  nginx_ssl_rewrite_site "$DEST" "rs.pttads.vn" || {
    cp "$backup" "$DEST"
    exit 1
  }
fi

nginx -t
systemctl reload nginx
echo "OK    nginx reloaded ($DEST)"
