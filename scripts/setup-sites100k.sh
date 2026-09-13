#!/usr/bin/env bash
# Switch the daily job from the 1,000-site lab list to 100,000 sites.
#   cd /root/crawl-policy-index && git pull && bash scripts/setup-sites100k.sh
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

echo "Building panel-sites100k from pinned Tranco list 94XL2..."
echo "This downloads a large list and can take a few minutes."
if ! python3 "$ROOT/panel/build_panel.py" \
  --version sites100k \
  --tranco-top 150000 \
  --keep 100000 \
  --drop-infra \
  --tranco-id 94XL2 \
  --out-dir "$ROOT/data"; then
  echo "Top 150k did not yield 100k non-infra names. Trying top 200k..."
  python3 "$ROOT/panel/build_panel.py" \
    --version sites100k \
    --tranco-top 200000 \
    --keep 100000 \
    --drop-infra \
    --tranco-id 94XL2 \
    --out-dir "$ROOT/data"
fi

if ! grep -q '^CPI_PANEL=' "$ROOT/.env"; then
  printf '\nCPI_PANEL=sites100k\n' >> "$ROOT/.env"
else
  sed -i 's/^CPI_PANEL=.*/CPI_PANEL=sites100k/' "$ROOT/.env"
fi

chmod +x "$ROOT/scripts/daily-fetch.sh" "$ROOT/scripts/daily-run.sh" "$ROOT/scripts/warehouse-once.sh"

echo ""
echo "Active panel is sites100k (100,000 sites). Still a test list — not the web."
echo "First fetch is about 30–50 minutes, then warehouse. Leave the box alone."
echo "Log: $ROOT/data/logs/daily.log"
echo ""
nohup bash "$ROOT/scripts/daily-run.sh" >/dev/null 2>&1 &
echo "Started. Watch: tail -f $ROOT/data/logs/daily.log"
echo "When it prints ok, reload the site. Cron keeps 02:00 UTC after that."
