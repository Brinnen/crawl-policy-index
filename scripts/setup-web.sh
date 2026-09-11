#!/usr/bin/env bash
# Serve the identity site (homepage + /bot) over HTTP, then HTTPS if possible.
#   bash scripts/setup-web.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${CPI_DOMAIN:-crawlpolicyindex.org}"
EMAIL="${CPI_CERT_EMAIL:-exclude@${DOMAIN}}"
export DEBIAN_FRONTEND=noninteractive

if [[ ! -f "$ROOT/site/identity/index.html" ]]; then
  echo "Missing $ROOT/site/identity/index.html"
  echo "Run: cd ~/crawl-policy-index && git pull"
  exit 1
fi

apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx

mkdir -p /var/www/cpi/bot /var/www/cpi/snapshot /etc/nginx/snippets
cp "$ROOT/site/identity/index.html" "$ROOT/site/identity/style.css" /var/www/cpi/
cp "$ROOT/site/identity/bot/index.html" /var/www/cpi/bot/
install -m 644 "$ROOT/site/identity/nginx-snapshot.conf" /etc/nginx/snippets/cpi-snapshot.conf

rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/default.conf

if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
  cp "$ROOT/site/identity/nginx.conf" /etc/nginx/sites-available/cpi
fi
ln -sfn /etc/nginx/sites-available/cpi /etc/nginx/sites-enabled/cpi

nginx -t
systemctl enable nginx
systemctl reload nginx

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable || true
fi

if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
  echo "Requesting Let's Encrypt certificate for ${DOMAIN} and www.${DOMAIN}..."
  certbot --nginx \
    -d "$DOMAIN" \
    -d "www.${DOMAIN}" \
    --redirect \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL"
fi

echo ""
echo "Open:"
echo "  https://${DOMAIN}/"
echo "  https://${DOMAIN}/bot/"
echo "If HTTPS times out, allow TCP 443 in DigitalOcean → Networking → Firewalls."
