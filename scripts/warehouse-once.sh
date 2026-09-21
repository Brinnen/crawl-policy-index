#!/usr/bin/env bash
# Load the droplet store into Postgres and derive lab policy intervals.
# Called by scripts/daily-run.sh. Manual:
#   bash scripts/warehouse-once.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]] || ! grep -q '^DATABASE_DSN=' "$ROOT/.env"; then
  echo "No DATABASE_DSN. Run: bash scripts/setup-postgres.sh"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

PANEL="${CPI_PANEL:-sites1000}"
CSV="$ROOT/data/panel-${PANEL}.csv"
MANIFEST="$ROOT/data/panel-${PANEL}.manifest.json"
if [[ ! -f "$CSV" || ! -f "$MANIFEST" ]]; then
  echo "missing panel $CSV — run: bash $ROOT/scripts/setup-sites100k.sh or setup-sites1m.sh"
  exit 1
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
export PYTHONPATH="$ROOT/parser:$ROOT/warehouse:$ROOT/warehouse/load"

echo "Applying migrations..."
python3 "$ROOT/warehouse/migrations/apply.py"

echo "Loading agents..."
python3 "$ROOT/warehouse/load/load_agents.py"

echo "Loading panel ${PANEL}..."
python3 "$ROOT/warehouse/load/load_panel.py" \
  --csv "$CSV" \
  --manifest "$MANIFEST"

echo "Loading observations..."
python3 "$ROOT/warehouse/load/load_observations.py" --store "$ROOT/data/store"

echo "Deriving robots.txt intervals for ${PANEL}..."
python3 "$ROOT/warehouse/derive/derive_robots.py" \
  --store "$ROOT/data/store" \
  --panel-version "$PANEL"

echo "Deriving homepage language (one-shot, existing rows kept)..."
python3 "$ROOT/warehouse/derive/derive_language.py" \
  --store "$ROOT/data/store" \
  --panel-version "$PANEL"

echo ""
python3 "$ROOT/warehouse/query_lab.py"
