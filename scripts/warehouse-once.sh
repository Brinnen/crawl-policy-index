#!/usr/bin/env bash
# Load the droplet store into Postgres and derive lab policy intervals.
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

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
export PYTHONPATH="$ROOT/parser:$ROOT/warehouse:$ROOT/warehouse/load"

echo "Applying migrations..."
python3 "$ROOT/warehouse/migrations/apply.py"

echo "Loading agents..."
python3 "$ROOT/warehouse/load/load_agents.py"

echo "Loading panel..."
python3 "$ROOT/warehouse/load/load_panel.py" \
  --csv "$ROOT/data/panel-sites1000.csv" \
  --manifest "$ROOT/data/panel-sites1000.manifest.json"

echo "Loading observations..."
python3 "$ROOT/warehouse/load/load_observations.py" --store "$ROOT/data/store"

echo "Deriving robots.txt intervals..."
python3 "$ROOT/warehouse/derive/derive_robots.py" --store "$ROOT/data/store"

echo ""
python3 "$ROOT/warehouse/query_lab.py"
