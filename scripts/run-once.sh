#!/usr/bin/env bash
# One fetch of the 32-site panel, then print the allow/block table.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH=/usr/local/go/bin:$PATH
export PYTHONPATH="$ROOT/parser"

cd "$ROOT"
if [[ ! -x fetcher/cpifetch ]]; then
  echo "fetcher/cpifetch is missing. Run: bash scripts/setup-droplet.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

mkdir -p data/store
echo "Fetching 32 sites with the Go fetcher..."
(cd fetcher && ./cpifetch --config ../config/dev.yml --panel ../data/panel-mini.csv --once)

echo ""
python3 "$ROOT/scripts/obs_to_smoke.py" --store "$ROOT/data/store" --out "$ROOT/data/smoke"
python3 "$ROOT/scripts/policy_table.py" --input "$ROOT/data/smoke" --out "$ROOT/data/policy-table.csv"

echo ""
echo "Manifest:"
cat "$ROOT"/data/store/obs/manifest/*.json
echo ""
echo "Spreadsheet: $ROOT/data/policy-table.csv"
