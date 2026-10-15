#!/usr/bin/env bash
# Build the 1,000,000-site panel CSV. Does not switch CPI_PANEL and does not
# start a full 1M pass. Leftover-hours fill: bash scripts/fill-1m.sh
#   cd /root/crawl-policy-index && bash scripts/setup-sites1m.sh
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

chmod +x "$ROOT/scripts/fill-1m.sh" "$ROOT/scripts/daily-fetch.sh" "$ROOT/scripts/daily-run.sh"

echo ""
echo "Wrote data/panel-sites1m.csv. CPI_PANEL is unchanged (still the 100k product)."
echo "Fill leftover hours with: bash $ROOT/scripts/fill-1m.sh"
echo "That job stops at 01:50 UTC so the nightly 100k run can start."
