#!/usr/bin/env bash
# VPS TLS paths — all *.pttads.vn sites share one cert pair under /etc/nginx/ssl/.
# Source from deploy scripts: . "$(dirname "$0")/lib/nginx_ssl_paths.sh"
set -euo pipefail

nginx_ssl_dir="${NGINX_SSL_DIR:-/etc/nginx/ssl}"
PTT_NGINX_SSL_CERT_DEFAULT="${nginx_ssl_dir}/portalpttadsvn.pem"
PTT_NGINX_SSL_KEY_DEFAULT="${nginx_ssl_dir}/portalpttadsvn.key"

nginx_ssl_resolve() {
  local domain="${1:-}"

  NGINX_SSL_CERT="${PTT_NGINX_SSL_CERT:-$PTT_NGINX_SSL_CERT_DEFAULT}"
  NGINX_SSL_KEY="${PTT_NGINX_SSL_KEY:-$PTT_NGINX_SSL_KEY_DEFAULT}"

  if [[ -f "$NGINX_SSL_CERT" && -f "$NGINX_SSL_KEY" ]]; then
    export NGINX_SSL_CERT NGINX_SSL_KEY
    return 0
  fi

  local cert="" key="" c k
  if [[ -n "$domain" ]]; then
    for c in \
      "$nginx_ssl_dir/${domain}.crt" \
      "$nginx_ssl_dir/${domain}.pem" \
      "$nginx_ssl_dir/${domain}-fullchain.pem"; do
      [[ -z "$cert" && -f "$c" ]] && cert="$c"
    done
    for k in \
      "$nginx_ssl_dir/${domain}.key" \
      "$nginx_ssl_dir/${domain}-privkey.pem"; do
      [[ -z "$key" && -f "$k" ]] && key="$k"
    done
  fi

  [[ -z "$cert" && -f "$PTT_NGINX_SSL_CERT_DEFAULT" ]] && cert="$PTT_NGINX_SSL_CERT_DEFAULT"
  [[ -z "$key" && -f "$PTT_NGINX_SSL_KEY_DEFAULT" ]] && key="$PTT_NGINX_SSL_KEY_DEFAULT"

  if [[ -z "$cert" || -z "$key" ]]; then
    echo "FAIL  SSL not found (expected $PTT_NGINX_SSL_CERT_DEFAULT + $PTT_NGINX_SSL_KEY_DEFAULT)" >&2
    ls -la "$nginx_ssl_dir" 2>/dev/null || true
    return 1
  fi

  NGINX_SSL_CERT="$cert"
  NGINX_SSL_KEY="$key"
  export NGINX_SSL_CERT NGINX_SSL_KEY
}

nginx_ssl_rewrite_site() {
  local site_file="${1:?nginx site file}"
  local domain="${2:-}"

  nginx_ssl_resolve "$domain"

  sed -i \
    -e "s|/etc/letsencrypt/live/[^/]*/fullchain.pem|${NGINX_SSL_CERT}|g" \
    -e "s|/etc/letsencrypt/live/[^/]*/privkey.pem|${NGINX_SSL_KEY}|g" \
    -e "s|/etc/nginx/ssl/fullchain.pem|${NGINX_SSL_CERT}|g" \
    -e "s|/etc/nginx/ssl/privkey.pem|${NGINX_SSL_KEY}|g" \
    -e "s|/etc/nginx/ssl/portalpttadsvn.pem|${NGINX_SSL_CERT}|g" \
    -e "s|/etc/nginx/ssl/portalpttadsvn.key|${NGINX_SSL_KEY}|g" \
    "$site_file"

  sed -i \
    -e '/include \/etc\/letsencrypt\/options-ssl-nginx.conf;/d' \
    -e '/ssl_dhparam \/etc\/letsencrypt\/ssl-dhparams.pem;/d' \
    "$site_file"

  if ! grep -q 'ssl_protocols' "$site_file"; then
    sed -i "/ssl_certificate_key/a\\
    ssl_protocols TLSv1.2 TLSv1.3;\\
    ssl_prefer_server_ciphers off;" "$site_file"
  fi

  echo "SSL  cert=$NGINX_SSL_CERT key=$NGINX_SSL_KEY"
}
