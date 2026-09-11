#!/usr/bin/env bash
# Install PostgreSQL 16 on the droplet, localhost only. Run as root:
#   bash scripts/setup-postgres.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y postgresql postgresql-contrib

systemctl enable --now postgresql

if ! grep -q '^DATABASE_DSN=' "$ROOT/.env" 2>/dev/null; then
  PASS="$(openssl rand -hex 16)"
  touch "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  printf 'DATABASE_DSN=postgresql://cpi:%s@127.0.0.1:5432/cpi\n' "$PASS" >>"$ROOT/.env"
  echo "Wrote DATABASE_DSN to $ROOT/.env"
fi

PASS="$(python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlparse, unquote
for line in Path(".env").read_text().splitlines():
    if line.startswith("DATABASE_DSN="):
        u = urlparse(line.split("=", 1)[1].strip())
        print(unquote(u.password or "cpi"))
        break
PY
)"

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cpi') THEN
    CREATE ROLE cpi LOGIN PASSWORD '${PASS}';
  ELSE
    ALTER ROLE cpi PASSWORD '${PASS}';
  END IF;
END
\$\$;
ALTER ROLE cpi SUPERUSER;
SELECT 'CREATE DATABASE cpi OWNER cpi'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'cpi')\gexec
SQL

# Do not listen on the public interface.
CONF="$(sudo -u postgres psql -tAc "SHOW config_file")"
if [[ -n "$CONF" ]] && grep -qE "^#?listen_addresses" "$CONF"; then
  sed -i "s/^#\?listen_addresses.*/listen_addresses = 'localhost'/" "$CONF"
fi
systemctl reload postgresql || systemctl restart postgresql

echo ""
echo "Postgres is on 127.0.0.1:5432 only (not the public internet)."
echo "Next: bash scripts/warehouse-once.sh"
