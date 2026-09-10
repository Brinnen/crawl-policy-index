#!/usr/bin/env python3
"""Apply warehouse/migrations/*.sql in lexical order. Forward-only."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent


def main() -> int:
    dsn = os.environ.get("DATABASE_DSN", "postgresql://cpi:cpi@localhost:5432/cpi")
    files = sorted(DIR.glob("*.sql"))
    if not files:
        print("no migrations", file=sys.stderr)
        return 1
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            for path in files:
                cur.execute("SELECT 1 FROM schema_migrations WHERE filename = %s", (path.name,))
                if cur.fetchone():
                    print(f"skip {path.name}")
                    continue
                sql = path.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
                print(f"applied {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
