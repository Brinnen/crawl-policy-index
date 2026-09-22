#!/usr/bin/env bash
# Put language / type / country onto the paid table.
# Does not fetch. Does not rebuild cpifetch. Safe while a fetch is running.
#   export CPI_PANEL=sites100k
#   bash scripts/refresh-lookup.sh
set -euo pipefail

ROOT="${CPI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PANEL="${CPI_PANEL:-sites100k}"
CSV="$ROOT/data/panel-${PANEL}.csv"
MANIFEST="$ROOT/data/panel-${PANEL}.manifest.json"
if [[ ! -f "$CSV" || ! -f "$MANIFEST" ]]; then
  echo "missing panel $CSV" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
export PYTHONPATH="$ROOT/parser:$ROOT/warehouse:$ROOT/warehouse/load:$ROOT/panel"

html_files=$(find "$ROOT/data/store/obs" -type f -name '*.ndjson' 2>/dev/null | grep -c html_home || true)
echo "html_home observation files: ${html_files}"

echo "Loading panel ${PANEL} with current labels..."
python3 "$ROOT/warehouse/load/load_panel.py" --csv "$CSV" --manifest "$MANIFEST"

echo "Loading observations already on disk..."
python3 "$ROOT/warehouse/load/load_observations.py" --store "$ROOT/data/store"

echo "Deriving language and site type from html_home..."
python3 "$ROOT/warehouse/derive/derive_language.py" \
  --store "$ROOT/data/store" \
  --panel-version "$PANEL"

echo "Exporting lookup + preview..."
python3 "$ROOT/warehouse/export_lab.py" --panel-version "$PANEL"
bash "$ROOT/scripts/publish-lab.sh"

echo "Paid table snapshot is at http://127.0.0.1/snapshot/lookup.json"
