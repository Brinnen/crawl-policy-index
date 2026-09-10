"""Load registry/agents.yml into the agent table. Never edit the table by hand."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running without installing the package.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "parser"))

from cpi_parser.registry import load_agents  # noqa: E402


UPSERT = """
INSERT INTO agent (slug, ua_token, display_name, operator, purpose, documented_url, verified, active, notes)
VALUES (%(slug)s, %(ua_token)s, %(display_name)s, %(operator)s, %(purpose)s, %(documented_url)s, %(verified)s, %(active)s, %(notes)s)
ON CONFLICT (slug) DO UPDATE SET
    ua_token = EXCLUDED.ua_token,
    display_name = EXCLUDED.display_name,
    operator = EXCLUDED.operator,
    purpose = EXCLUDED.purpose,
    documented_url = EXCLUDED.documented_url,
    verified = EXCLUDED.verified,
    active = EXCLUDED.active,
    notes = EXCLUDED.notes;
"""


def rows_from_yaml(path: Path) -> list[dict]:
    return [
        {
            "slug": a.slug,
            "ua_token": a.ua_token,
            "display_name": a.display_name,
            "operator": a.operator,
            "purpose": a.purpose,
            "documented_url": a.documented_url,
            "verified": a.verified,
            "active": a.active,
            "notes": a.notes,
        }
        for a in load_agents(path)
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", default=str(ROOT / "registry" / "agents.yml"))
    p.add_argument("--dsn", default=os.environ.get("DATABASE_DSN", "postgresql://cpi:cpi@localhost:5432/cpi"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    rows = rows_from_yaml(Path(args.registry))
    if any(r["verified"] for r in rows):
        print("warning: verified=true present; confirm each token against operator docs", file=sys.stderr)
    if args.dry_run:
        print(f"{len(rows)} agents, all unverified={all(not r['verified'] for r in rows)}")
        return 0
    import psycopg

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(UPSERT, row)
        conn.commit()
    print(f"loaded {len(rows)} agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
