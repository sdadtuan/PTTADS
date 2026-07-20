#!/usr/bin/env bash
# Install nginx snippet for webhook v1 upstream routing (Phase 0 P0-4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-nest-meta}"
SNIPPET_SRC="$ROOT/deploy/nginx-webhooks-v1-cutover.conf"
SNIPPET_DST="${NGINX_SNIPPET_DST:-/etc/nginx/snippets/ptt-webhooks-v1-routing.conf}"

if [[ ! -f "$SNIPPET_SRC" ]]; then
  echo "Missing $SNIPPET_SRC" >&2
  exit 1
fi

case "$MODE" in
  nest-meta)
    echo "==> Installing NEST-META webhook routing → $SNIPPET_DST"
    sudo cp "$SNIPPET_SRC" "$SNIPPET_DST"
    ;;
  nest-all)
    ALL_SRC="$ROOT/deploy/nginx-webhooks-v1-upstream-nest-all.conf"
    if [[ ! -f "$ALL_SRC" ]]; then
      echo "Missing $ALL_SRC" >&2
      exit 1
    fi
    echo "==> Installing NEST-ALL webhook routing → $SNIPPET_DST"
    sudo cp "$ALL_SRC" "$SNIPPET_DST"
    ;;
  flask)
    echo "==> Installing FLASK rollback webhook routing"
    sudo tee "$SNIPPET_DST" >/dev/null <<'EOF'
# Rollback — all /api/v1/webhooks/* → Flask
upstream ptt_flask_app {
    server 127.0.0.1:8002;
    keepalive 8;
}
location ^~ /api/v1/webhooks/ {
    proxy_pass http://ptt_flask_app;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    client_max_body_size 2m;
}
location = /api/v1/channels {
    proxy_pass http://ptt_flask_app;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
}
EOF
    ;;
  *)
    echo "Usage: $0 [nest-meta|nest-all|flask]" >&2
    exit 2
    ;;
esac

echo "==> nginx -t"
sudo nginx -t
echo "==> reload nginx"
sudo systemctl reload nginx
echo "OK mode=$MODE"
