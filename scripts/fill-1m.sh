#!/usr/bin/env bash
# Leftover-hours robots.txt fill for sites1m. Does not change CPI_PANEL.
# Stops before 01:50 UTC so the 02:00 100k job can take the fetch lock.
#   bash scripts/fill-1m.sh
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ROOT="${CPI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

# Do not inherit daily-run flock fds.
exec 8>&- 9>&- 10>&- || true

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

mkdir -p "$ROOT/data/logs"
log="$ROOT/data/logs/fill-1m.log"

hm=$(date -u +%H%M)
if (( 10#$hm >= 150 && 10#$hm < 300 )); then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) skip: daily window" >>"$log"
  exit 0
fi

exec 10>"$ROOT/data/fill-1m.lock"
if ! flock -n 10; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) fill already running" >>"$log"
  exit 0
fi

exec 9>"$ROOT/data/fetch.lock"
if ! flock -n 9; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) fetch lock busy (100k job)" >>"$log"
  exit 0
fi

{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) fill-1m start ===="

  if [[ ! -x /sbin/swapon ]] && ! command -v swapon >/dev/null; then
    true
  elif [[ -z "$(swapon --show --noheadings 2>/dev/null || true)" ]]; then
    echo "adding 4G swap"
    if [[ ! -f /swapfile ]]; then
      fallocate -l 4G /swapfile
      chmod 600 /swapfile
      mkswap /swapfile
    fi
    swapon /swapfile || true
    if [[ -f /etc/fstab ]] && ! grep -q '^/swapfile ' /etc/fstab; then
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
  fi

  if [[ ! -f "$ROOT/data/panel-sites1m.csv" ]]; then
    echo "building panel-sites1m (one-time)"
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
    if ! python3 "$ROOT/panel/build_panel.py" \
      --version sites1m \
      --tranco-top 1200000 \
      --keep 1000000 \
      --drop-infra \
      --tranco-id 94XL2 \
      --out-dir "$ROOT/data"; then
      python3 "$ROOT/panel/build_panel.py" \
        --version sites1m \
        --tranco-top 1500000 \
        --keep 1000000 \
        --drop-infra \
        --tranco-id 94XL2 \
        --out-dir "$ROOT/data"
    fi
  fi

  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  python3 "$ROOT/scripts/build-1m-queue.py" \
    --panel "$ROOT/data/panel-sites1m.csv" \
    --store "$ROOT/data/store" \
    --out "$ROOT/data/panel-sites1m-queue.csv" | tee "$ROOT/data/logs/fill-1m.queue"

  remaining=$(python3 -c "import csv; print(sum(1 for _ in csv.DictReader(open('$ROOT/data/panel-sites1m-queue.csv', encoding='utf-8'))))")
  echo "$remaining" >"$ROOT/data/logs/fill-1m.remaining"
  if [[ "$remaining" -eq 0 ]]; then
    echo "queue empty — 1M robots pass is on disk. CPI_PANEL is still sites100k."
    echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) fill-1m done ===="
    exit 0
  fi

  secs=$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
target = now.replace(hour=1, minute=50, second=0, microsecond=0)
if now >= target:
    target += timedelta(days=1)
print(max(0, int((target - now).total_seconds()) - 30))
PY
)
  if [[ "$secs" -lt 120 ]]; then
    echo "not enough time before 01:50 UTC ($secs s)"
    exit 0
  fi

  cd "$ROOT/fetcher"
  if command -v go >/dev/null 2>&1; then
    go build -o cpifetch ./cmd/cpifetch
  fi
  if [[ ! -x ./cpifetch ]]; then
    echo "missing fetcher/cpifetch" >&2
    exit 1
  fi

  echo "fetching $remaining sites, stop in ${secs}s (01:50 UTC)"
  set +e
  timeout --signal=TERM --kill-after=90 "$secs" ./cpifetch \
    --config "$ROOT/config/droplet-sites1m-robots.yml" \
    --panel "$ROOT/data/panel-sites1m-queue.csv" \
    --once
  rc=$?
  set -e
  if [[ "$rc" -eq 124 ]] || [[ "$rc" -eq 143 ]]; then
    echo "stopped for the 02:00 UTC 100k job"
  elif [[ "$rc" -ne 0 ]]; then
    echo "WARNING: cpifetch exited $rc"
  fi

  python3 "$ROOT/scripts/build-1m-queue.py" \
    --panel "$ROOT/data/panel-sites1m.csv" \
    --store "$ROOT/data/store" \
    --out "$ROOT/data/panel-sites1m-queue.csv" | tee "$ROOT/data/logs/fill-1m.queue"
  remaining=$(python3 -c "import csv; print(sum(1 for _ in csv.DictReader(open('$ROOT/data/panel-sites1m-queue.csv', encoding='utf-8'))))")
  echo "$remaining" >"$ROOT/data/logs/fill-1m.remaining"
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) fill-1m stop remaining=$remaining ===="
} >>"$log" 2>&1
