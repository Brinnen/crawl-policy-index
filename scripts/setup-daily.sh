#!/usr/bin/env bash
# One-time: install the daily pipeline and the public snapshot URL.
#   cd /root/crawl-policy-index && git pull && bash scripts/setup-daily.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this as root on the droplet."
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

chmod +x "$ROOT/scripts/daily-fetch.sh" "$ROOT/scripts/daily-run.sh" "$ROOT/scripts/publish-lab.sh" "$ROOT/scripts/warehouse-once.sh"

mkdir -p "$ROOT/data/logs" /var/www/cpi/snapshot /etc/nginx/snippets
if [[ -f "$ROOT/site/tracker/src/data/lab.json" ]]; then
  cp "$ROOT/site/tracker/src/data/lab.json" /var/www/cpi/snapshot/lab.json
  chmod 644 /var/www/cpi/snapshot/lab.json
fi

install -m 644 "$ROOT/site/identity/nginx-snapshot.conf" /etc/nginx/snippets/cpi-snapshot.conf

python3 - "$ROOT" <<'PY'
from pathlib import Path
import shutil
import sys

nginx = Path("/etc/nginx/sites-available/cpi")
if not nginx.exists():
    print("No /etc/nginx/sites-available/cpi yet. Run bash scripts/setup-web.sh first, then re-run this.")
    sys.exit(0)

text = nginx.read_text(encoding="utf-8")
if "cpi-snapshot.conf" in text or "location /snapshot/" in text:
    print("nginx already serves /snapshot/")
    sys.exit(0)

backup = nginx.with_suffix(".conf.bak-snapshot")
shutil.copyfile(nginx, backup)

needle = "location / {"
insert = "include snippets/cpi-snapshot.conf;\n\n    location / {"
if needle not in text:
    print("Could not find 'location / {' in nginx config. Add the snapshot location by hand.")
    print("See site/identity/nginx-snapshot.conf")
    sys.exit(1)

text = text.replace(needle, insert)
nginx.write_text(text, encoding="utf-8")
print(f"patched {nginx} (backup {backup})")
PY

if nginx -t; then
  systemctl reload nginx
else
  bak="/etc/nginx/sites-available/cpi.conf.bak-snapshot"
  if [[ -f "$bak" ]]; then
    cp "$bak" /etc/nginx/sites-available/cpi
    echo "nginx test failed; restored the previous site config."
  fi
  exit 1
fi

cat > /etc/cron.d/crawl-policy-index <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""
0 2 * * * root ${ROOT}/scripts/daily-run.sh
EOF
chmod 644 /etc/cron.d/crawl-policy-index

echo ""
echo "Daily job: 02:00 UTC — fetch, warehouse, export, publish."
echo "Live numbers: https://crawlpolicyindex.org/snapshot/lab.json"
echo "Log: ${ROOT}/data/logs/daily.log"

if grep -qE '^GITHUB_TOKEN=.' "$ROOT/.env" 2>/dev/null; then
  echo "GITHUB_TOKEN is set — the job will also commit lab.json for Vercel."
else
  echo ""
  echo "Optional: add GITHUB_TOKEN to ${ROOT}/.env if you want Vercel to rebuild"
  echo "domain pages by itself. Fine-grained PAT, Contents: Read and write, this repo only."
  echo "Without it, overview and Explore still update from the snapshot URL."
fi

echo ""
echo "Starting the first pipeline in the background (fetch may take a while)..."
nohup bash "$ROOT/scripts/daily-run.sh" >/dev/null 2>&1 &
echo "Watch progress: tail -f ${ROOT}/data/logs/daily.log"
echo "When it prints ok, the site will pick up new numbers on the next page load."
