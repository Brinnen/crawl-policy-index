"""Export lab warehouse views to the Astro tracker data file.

Run on the droplet after warehouse-once.sh:

    python3 warehouse/export_lab.py

Then copy site/tracker/src/data/lab.json into git so Vercel rebuilds from the snapshot.
Vercel cannot reach Postgres on the droplet.

The tracker does not publish this file as a download. It is a build input.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from warehouse.dsn import database_dsn  # noqa: E402
from warehouse.load.org_group import group_key  # noqa: E402

OUT = ROOT / "site" / "tracker" / "src" / "data" / "lab.json"

NAMED_SQL = """
SELECT
    pi.domain,
    pi.state::text,
    pi.valid_from::text,
    a.slug,
    a.ua_token,
    a.display_name,
    a.operator,
    a.purpose::text
FROM policy_interval pi
JOIN agent a ON a.slug = pi.agent_slug
WHERE pi.valid_to IS NULL
ORDER BY pi.domain, a.operator, a.slug
"""

BY_AGENT_SQL = """
SELECT
    a.slug,
    a.ua_token,
    a.display_name,
    a.operator,
    a.purpose::text,
    count(*) FILTER (WHERE pi.state = 'BLOCKED'),
    count(*) FILTER (WHERE pi.state = 'ALLOWED'),
    count(*) FILTER (WHERE pi.state = 'PARTIAL')
FROM agent a
JOIN policy_interval pi
  ON pi.agent_slug = a.slug
 AND pi.valid_to IS NULL
GROUP BY a.slug, a.ua_token, a.display_name, a.operator, a.purpose
ORDER BY count(*) FILTER (WHERE pi.state = 'BLOCKED') DESC, a.operator, a.slug
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)

    import psycopg

    dsn = args.dsn or database_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fetch_observation WHERE resource = 'robots_txt'")
            obs = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM wildcard_interval WHERE valid_to IS NULL")
            wild = cur.fetchone()[0]
            cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE state = 'BLOCKED'),
                    count(*) FILTER (WHERE state = 'ALLOWED'),
                    count(*) FILTER (WHERE state = 'PARTIAL')
                FROM v_lab_gptbot_named
                """
            )
            named_block, named_allow, named_partial = cur.fetchone()
            cur.execute(
                """
                SELECT count(*) FILTER (WHERE named_block_rows > 0)
                FROM v_lab_gptbot_named_grouped
                """
            )
            grouped_block = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM policy_interval gpt
                LEFT JOIN policy_interval search
                  ON search.domain = gpt.domain
                 AND search.valid_to IS NULL
                 AND search.agent_slug = 'openai-searchbot'
                WHERE gpt.agent_slug = 'openai-gptbot'
                  AND gpt.valid_to IS NULL
                  AND gpt.state = 'BLOCKED'
                  AND COALESCE(search.state::text, '') IS DISTINCT FROM 'BLOCKED'
                """
            )
            split = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM policy_interval
                WHERE agent_slug = 'google-googlebot'
                  AND state = 'BLOCKED'
                  AND valid_to IS NULL
                """
            )
            google_block = cur.fetchone()[0]
            cur.execute(NAMED_SQL)
            named = [
                {
                    "domain": domain,
                    "state": state,
                    "valid_from": vf,
                    "agent_slug": slug,
                    "token": token,
                    "agent": display,
                    "operator": operator,
                    "purpose": purpose,
                    "group_key": group_key(domain),
                }
                for domain, state, vf, slug, token, display, operator, purpose in cur.fetchall()
            ]
            cur.execute(BY_AGENT_SQL)
            by_agent = [
                {
                    "slug": slug,
                    "token": token,
                    "agent": display,
                    "operator": operator,
                    "purpose": purpose,
                    "named_block": block,
                    "named_allow": allow,
                    "named_partial": partial,
                }
                for slug, token, display, operator, purpose, block, allow, partial in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT group_key, domain_rows, named_block_rows, named_allow_rows, named_partial_rows
                FROM v_lab_gptbot_named_grouped
                ORDER BY named_block_rows DESC, group_key
                """
            )
            grouped = [
                {
                    "group_key": g,
                    "domain_rows": dr,
                    "named_block_rows": nb,
                    "named_allow_rows": na,
                    "named_partial_rows": np,
                }
                for g, dr, nb, na, np in cur.fetchall()
            ]

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "panel_version": "sites1000",
        "parse_version": "1.0.0",
        "view": "policy_interval",
        "lab": True,
        "verified_agents": False,
        "summary": {
            "trusted_robots": wild,
            "gptbot_named_block": named_block,
            "gptbot_named_allow": named_allow,
            "gptbot_named_partial": named_partial,
            "gptbot_named_block_grouped": grouped_block,
            "openai_split": split,
            "googlebot_named_block": google_block,
            "calendar_observations": obs,
        },
        "by_agent": by_agent,
        "named": named,
        "grouped": grouped,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(named)} named rows, {len(by_agent)} agents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
