#!/usr/bin/env bash
# Issue/renew Let's Encrypt cert for portal.pttads.vn and install nginx site (Phase 3 prod)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${PTT_PORTAL_DOMAIN:-portal.pttads.vn}"
EMAIL="${CERTBOT_EMAIL:-ops@pttads.vn}"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on VPS: sudo $0" >&2
  exit 1
fi

if ! command -v certbot >/dev/null 2>&1; then
  echo "==> Installing certbot + nginx plugin"
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx
fi

echo "==> Pre-flight: DNS A/AAAA for $DOMAIN must point to this host"
getent hosts "$DOMAIN" || true

echo "==> Install nginx site config"
cp "$ROOT/deploy/nginx-portal.conf" "$NGINX_SITE"
sed -i "s/portal.pttads.vn/${DOMAIN}/g" "$NGINX_SITE"
ln -sf "$NGINX_SITE" "$NGINX_ENABLED"
nginx -t

if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "==> certbot certonly (nginx) for $DOMAIN"
  certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"
else
  echo "==> Cert exists — renew if needed"
  certbot renew --nginx --quiet || true
fi

echo "==> Reload nginx"
systemctl reload nginx

echo "OK  https://${DOMAIN}/login"
echo "    Renew timer: systemctl list-timers | grep certbot"
