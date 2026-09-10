#!/usr/bin/env bash
# Usage:
#   bash scripts/run-once.sh          # 32-site smoke panel, 3 files each
#   bash scripts/run-once.sh 1000     # raw Tranco top 1000 (includes CDNs)
#   bash scripts/run-once.sh sites    # first 1000 non-infra sites from Tranco 94XL2
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH=/usr/local/go/bin:$PATH
export PYTHONPATH="$ROOT/parser:$ROOT/panel"

SIZE="${1:-32}"
cd "$ROOT"
if [[ ! -x fetcher/cpifetch ]]; then
  echo "fetcher/cpifetch is missing. Run: bash scripts/setup-droplet.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

if [[ "$SIZE" == "sites" ]]; then
  echo "Building first 1000 non-infra sites from pinned Tranco list 94XL2..."
  python3 panel/build_panel.py --version sites1000 --tranco-top 3000 --keep 1000 --drop-infra --tranco-id 94XL2 --out-dir data
  PANEL="$ROOT/data/panel-sites1000.csv"
  CONFIG="$ROOT/config/droplet-sites1000.yml"
  echo "Fetching robots.txt for 1000 websites. This can take 10–20 minutes. Leave this window open."
elif [[ "$SIZE" == "1000" ]]; then
  echo "Building pinned Tranco top-1000 panel (list 94XL2)..."
  python3 panel/build_panel.py --version tranco1000 --tranco-top 1000 --tranco-id 94XL2 --out-dir data
  PANEL="$ROOT/data/panel-tranco1000.csv"
  CONFIG="$ROOT/config/droplet1000.yml"
  echo "Fetching robots.txt for 1000 sites. This can take 10–20 minutes. Leave this window open."
else
  PANEL="$ROOT/data/panel-mini.csv"
  CONFIG="$ROOT/config/dev.yml"
  echo "Fetching 32 sites with the Go fetcher..."
fi

mkdir -p data/store
(cd fetcher && ./cpifetch --config "$CONFIG" --panel "$PANEL" --once)

echo ""
rm -rf "$ROOT/data/smoke"
SMOKE_DATE=""
if [[ -n "${RUN_DATE:-}" ]]; then
  SMOKE_DATE="--run-date $RUN_DATE"
fi
python3 "$ROOT/scripts/obs_to_smoke.py" --store "$ROOT/data/store" --out "$ROOT/data/smoke" $SMOKE_DATE
if [[ "$SIZE" == "1000" || "$SIZE" == "sites" ]]; then
  python3 "$ROOT/scripts/policy_table.py" --input "$ROOT/data/smoke" --out "$ROOT/data/policy-table.csv" --print-rows 0
else
  python3 "$ROOT/scripts/policy_table.py" --input "$ROOT/data/smoke" --out "$ROOT/data/policy-table.csv"
fi

echo ""
echo "Manifest:"
cat "$ROOT"/data/store/obs/manifest/*.json
echo ""
echo "Spreadsheet: $ROOT/data/policy-table.csv"
