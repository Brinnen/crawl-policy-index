#!/usr/bin/env bash
# Old location. Forwards to scripts/setup-web.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$ROOT/scripts/setup-web.sh"
