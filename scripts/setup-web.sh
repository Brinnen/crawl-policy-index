#!/usr/bin/env bash
# Serve the identity site (homepage + /bot). Run from anywhere, as root:
#   bash scripts/setup-web.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEBIAN_FRONTEND=noninteractive

if [[ ! -f "$ROOT/site/identity/index.html" ]]; then
  echo "Missing $ROOT/site/identity/index.html"
  echo "Run: cd ~/crawl-policy-index && git pull"
  exit 1
fi

apt-get update -y
apt-get install -y nginx

mkdir -p /var/www/cpi/bot
cp "$ROOT/site/identity/index.html" "$ROOT/site/identity/style.css" /var/www/cpi/
cp "$ROOT/site/identity/bot/index.html" /var/www/cpi/bot/

rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/default.conf
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
echo "Files in place:"
ls -la /var/www/cpi /var/www/cpi/bot
echo "Enabled sites:"
ls -la /etc/nginx/sites-enabled
echo ""
echo "Local check (should be HTTP 200 or 301):"
curl -sI http://127.0.0.1/bot | head -n 5
curl -sI http://127.0.0.1/bot/ | head -n 5
echo ""
echo "Open:"
echo "  http://178.128.255.20/"
echo "  http://178.128.255.20/bot/"
echo "If the browser still times out, allow TCP 80 in DigitalOcean → Networking → Firewalls."
