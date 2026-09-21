#!/usr/bin/env bash
# Daily robots.txt fetch for the active panel (CPI_PANEL). Called by daily-run.sh.
# Uses UTC today's date. Safe to re-run the same day: completed pairs are skipped.
set -euo pipefail

ROOT="${CPI_ROOT:-/root/crawl-policy-index}"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PANEL="${CPI_PANEL:-sites1000}"
CONFIG="$ROOT/config/droplet-${PANEL}.yml"
CSV="$ROOT/data/panel-${PANEL}.csv"

cd "$ROOT/fetcher"

if command -v go >/dev/null 2>&1; then
  echo "building fetcher..."
  go build -o cpifetch ./cmd/cpifetch
fi
if [[ ! -x ./cpifetch ]]; then
  echo "missing $ROOT/fetcher/cpifetch — run: bash $ROOT/scripts/setup-droplet.sh" >&2
  exit 1
fi
if [[ ! -f "$CONFIG" ]]; then
  echo "missing config $CONFIG" >&2
  exit 1
fi
if [[ ! -f "$CSV" ]]; then
  echo "missing panel $CSV — run: bash $ROOT/scripts/setup-sites100k.sh or setup-sites1m.sh" >&2
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
  echo "---- $(date -u +%Y-%m-%dT%H:%M:%SZ) start panel=${PANEL} ----"
  ./cpifetch \
    --config "$CONFIG" \
    --panel "$CSV" \
    --once
  echo "---- $(date -u +%Y-%m-%dT%H:%M:%SZ) end panel=${PANEL} ----"
} >>"$log" 2>&1
