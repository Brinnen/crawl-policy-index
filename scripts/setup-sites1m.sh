#!/usr/bin/env bash
# Switch the daily job to 1,000,000 sites (Tranco head, plus curated news).
# That is still a named panel, not the web.
#   cd /root/crawl-policy-index && git pull && bash scripts/setup-sites1m.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this as root on the droplet."
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "No .env. Run bash scripts/setup-postgres.sh first."
  exit 1
fi
if [[ ! -x "$ROOT/fetcher/cpifetch" ]]; then
  echo "missing fetcher/cpifetch — run: bash scripts/setup-droplet.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

echo "Building panel-sites1m from pinned Tranco list 94XL2..."
echo "This downloads a large list and can take several minutes."
if ! python3 "$ROOT/panel/build_panel.py" \
  --version sites1m \
  --tranco-top 1200000 \
  --keep 1000000 \
  --drop-infra \
  --tranco-id 94XL2 \
  --out-dir "$ROOT/data"; then
  echo "Top 1.2M did not yield 1M non-infra names. Trying top 1.5M..."
  python3 "$ROOT/panel/build_panel.py" \
    --version sites1m \
    --tranco-top 1500000 \
    --keep 1000000 \
    --drop-infra \
    --tranco-id 94XL2 \
    --out-dir "$ROOT/data"
fi

if ! grep -q '^CPI_PANEL=' "$ROOT/.env"; then
  printf '\nCPI_PANEL=sites1m\n' >> "$ROOT/.env"
else
  sed -i 's/^CPI_PANEL=.*/CPI_PANEL=sites1m/' "$ROOT/.env"
fi

chmod +x "$ROOT/scripts/daily-fetch.sh" "$ROOT/scripts/daily-run.sh" "$ROOT/scripts/warehouse-once.sh"

echo ""
echo "Active panel is sites1m (1,000,000 sites + curated news). Still not the web."
echo "First robots.txt pass is several hours. Homepage language is one-shot after that."
echo "Log: $ROOT/data/logs/daily.log"
echo ""
nohup bash "$ROOT/scripts/daily-run.sh" >/dev/null 2>&1 &
echo "Started. Watch: tail -f $ROOT/data/logs/daily.log"
echo "When it prints ok, reload the site. Cron keeps 02:00 UTC after that."
