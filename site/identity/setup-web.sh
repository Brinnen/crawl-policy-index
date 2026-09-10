#!/usr/bin/env bash
# Serve the identity site (homepage + /bot) with nginx. Run as root after the fetch finishes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y nginx

mkdir -p /var/www/cpi/bot
cp "$ROOT/site/identity/index.html" "$ROOT/site/identity/style.css" /var/www/cpi/
cp "$ROOT/site/identity/bot/index.html" /var/www/cpi/bot/
rm -f /etc/nginx/sites-enabled/default
cp "$ROOT/site/identity/nginx.conf" /etc/nginx/sites-available/cpi
ln -sfn /etc/nginx/sites-available/cpi /etc/nginx/sites-enabled/cpi
nginx -t
systemctl enable nginx
systemctl reload nginx

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw --force enable || true
fi

echo ""
echo "Site should be at:"
echo "  http://178.128.255.20/"
echo "  http://178.128.255.20/bot"
echo "If those time out, open DigitalOcean → Networking → Firewalls and allow TCP 80 inbound."
