#!/usr/bin/env bash
# Publish the latest lab.json. Snapshot on this host is the live numbers.
# Optional git push (GITHUB_TOKEN or an existing deploy key) rebuilds Vercel.
set -euo pipefail

ROOT="${CPI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

FILE="site/tracker/src/data/lab.json"
if [[ ! -f "$ROOT/$FILE" ]]; then
  echo "missing $ROOT/$FILE — export_lab.py did not run" >&2
  exit 1
fi

published=0

if mkdir -p /var/www/cpi/snapshot 2>/dev/null; then
  cp "$ROOT/$FILE" /var/www/cpi/snapshot/lab.json
  chmod 644 /var/www/cpi/snapshot/lab.json
  echo "snapshot https://crawlpolicyindex.org/snapshot/lab.json"
  LOOKUP="$ROOT/site/tracker/src/data/lookup.json"
  if [[ -f "$LOOKUP" ]]; then
    cp "$LOOKUP" /var/www/cpi/snapshot/lookup.json
    chmod 644 /var/www/cpi/snapshot/lookup.json
    echo "snapshot https://crawlpolicyindex.org/snapshot/lookup.json"
  else
    echo "WARNING: missing $LOOKUP — Explore website search will be empty" >&2
  fi
  published=1
else
  echo "WARNING: could not write /var/www/cpi/snapshot/lab.json" >&2
fi

token=""
if [[ -f "$ROOT/.env" ]]; then
  token="$(grep -E '^GITHUB_TOKEN=' "$ROOT/.env" | tail -n 1 | cut -d= -f2- | tr -d "\"'" || true)"
fi

git_push() {
  local origin
  if ! command -v git >/dev/null 2>&1; then
    return 1
  fi
  if [[ ! -d "$ROOT/.git" ]]; then
    return 1
  fi

  git add -- "$FILE"
  if git diff --cached --quiet -- "$FILE"; then
    echo "lab.json unchanged vs git index"
    return 0
  fi

  git -c user.name="Crawl Policy Index" -c user.email="bot@crawlpolicyindex.org" \
    commit -m "Lab snapshot $(date -u +%Y-%m-%d)" -- "$FILE"

  GIT_TERMINAL_PROMPT=0
  export GIT_TERMINAL_PROMPT

  origin="$(git remote get-url origin)"

  git fetch origin
  git pull --rebase origin master

  if [[ -n "$token" && "$origin" != git@* && "$origin" != ssh://* ]]; then
    git -c "http.extraHeader=Authorization: Bearer ${token}" push origin HEAD:master
    return
  fi

  git push origin HEAD:master
}

set +e
if git_push; then
  echo "git publish ok"
  published=1
else
  echo "git publish skipped or failed (snapshot on this host is still the live numbers)"
fi
set -e

if [[ "$published" -ne 1 ]]; then
  echo "publish failed: no snapshot and no git push" >&2
  exit 1
fi
