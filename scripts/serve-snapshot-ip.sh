#!/usr/bin/env bash
# Serve /snapshot/lab.json on the droplet IP (port 80).
# crawlpolicyindex.org points at Vercel; Vercel proxies this URL.
#   bash scripts/serve-snapshot-ip.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this as root on the droplet."
  exit 1
fi

FILE="/var/www/cpi/snapshot/lab.json"
if [[ ! -f "$FILE" ]]; then
  echo "missing $FILE — run: bash scripts/publish-lab.sh"
  exit 1
fi
chmod 644 "$FILE"

rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/sites-available/cpi-snapshot-ip <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location = /snapshot/lab.json {
        alias /var/www/cpi/snapshot/lab.json;
        default_type application/json;
        add_header Access-Control-Allow-Origin "*" always;
        add_header Cache-Control "public, max-age=60" always;
    }

    location /snapshot/ {
        alias /var/www/cpi/snapshot/;
        default_type application/json;
        add_header Access-Control-Allow-Origin "*" always;
        add_header Cache-Control "public, max-age=60" always;
    }

    location / {
        return 404;
    }
}
EOF

ln -sfn /etc/nginx/sites-available/cpi-snapshot-ip /etc/nginx/sites-enabled/cpi-snapshot-ip

if [[ -f /etc/nginx/sites-available/cpi ]]; then
  sed -i 's/ default_server//g' /etc/nginx/sites-available/cpi
fi

nginx -t
systemctl reload nginx

python3 - <<'PY'
import json, urllib.request
raw = urllib.request.urlopen("http://127.0.0.1/snapshot/lab.json", timeout=10).read()
data = json.loads(raw)
print("ok", data.get("panel_version"), data.get("summary", {}).get("panel_size"))
PY
