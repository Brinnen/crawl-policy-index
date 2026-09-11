#!/usr/bin/env bash
# One daily job: fetch → warehouse → export → publish.
# Install once: bash scripts/setup-daily.sh
# Cron: 02:00 UTC via /etc/cron.d/crawl-policy-index
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ROOT="${CPI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

mkdir -p "$ROOT/data/logs"
log="$ROOT/data/logs/daily.log"

exec 8>"$ROOT/data/pipeline.lock"
if ! flock -n 8; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) pipeline already running" >>"$log"
  exit 0
fi

{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) start ===="

  set +e
  CPI_FETCH_WAIT=1 bash "$ROOT/scripts/daily-fetch.sh"
  fetch_rc=$?
  set -e
  if [[ "$fetch_rc" -ne 0 ]]; then
    echo "WARNING: fetch exited ${fetch_rc}; warehousing whatever is already in the store"
  fi

  bash "$ROOT/scripts/warehouse-once.sh"
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  python3 "$ROOT/warehouse/export_lab.py"
  bash "$ROOT/scripts/publish-lab.sh"

  date -u +%Y-%m-%dT%H:%M:%SZ >"$ROOT/data/logs/last-ok"
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) ok ===="
} >>"$log" 2>&1
