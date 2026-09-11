#!/usr/bin/env bash
# Daily sites1000 robots.txt fetch. Called by scripts/daily-run.sh (the cron job).
# Uses UTC today's date. Safe to re-run the same day: completed pairs are skipped.
set -euo pipefail

ROOT="${CPI_ROOT:-/root/crawl-policy-index}"
cd "$ROOT/fetcher"

if [[ ! -x ./cpifetch ]]; then
  echo "missing $ROOT/fetcher/cpifetch — run: bash $ROOT/scripts/setup-droplet.sh" >&2
  exit 1
fi
if [[ ! -f "$ROOT/data/panel-sites1000.csv" ]]; then
  echo "missing panel $ROOT/data/panel-sites1000.csv" >&2
  exit 1
fi

mkdir -p "$ROOT/data/logs"
exec 9>"$ROOT/data/fetch.lock"
if [[ "${CPI_FETCH_WAIT:-}" == "1" ]]; then
  flock 9
elif ! flock -n 9; then
  echo "fetch already running" >&2
  exit 0
fi
log="$ROOT/data/logs/fetch.log"
{
  echo "---- $(date -u +%Y-%m-%dT%H:%M:%SZ) start ----"
  ./cpifetch \
    --config ../config/droplet-sites1000.yml \
    --panel ../data/panel-sites1000.csv \
    --once
  echo "---- $(date -u +%Y-%m-%dT%H:%M:%SZ) end ----"
} >>"$log" 2>&1
