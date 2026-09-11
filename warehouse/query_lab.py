"""Print lab GPTBot counts from Postgres. Not for publication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from warehouse.dsn import database_dsn  # noqa: E402


def main() -> int:
    import psycopg

    dsn = database_dsn()
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
                    count(*) FILTER (WHERE state = 'PARTIAL'),
                    count(*)
                FROM v_lab_gptbot_named
                """
            )
            named_block, named_allow, named_partial, named_total = cur.fetchone()
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
            cur.execute(
                """
                SELECT count(*)
                FROM wildcard_interval wi
                WHERE wi.valid_to IS NULL
                  AND wi.has_wildcard_group
                  AND wi.state = 'BLOCKED'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM policy_interval pi
                    WHERE pi.domain = wi.domain
                      AND pi.agent_slug = 'openai-gptbot'
                      AND pi.valid_to IS NULL
                  )
                """
            )
            gptbot_blanket = cur.fetchone()[0]

    print("Lab warehouse — NOT for publication (agents are unverified)")
    print(f"  calendar robots observations: {obs}")
    print(f"  domains with a trusted robots.txt (open wildcard interval): {wild}")
    print(f"  GPTBot named rows: {named_total}  block={named_block} allow={named_allow} partial={named_partial}")
    print(f"  GPTBot named BLOCK after collapsing amazon.*: {grouped_block}")
    print(f"  named GPTBot block but OpenAI search not blocked: {split}")
    print(f"  GPTBot blocked only via block-all-bots (*): {gptbot_blanket}")
    print(f"  Googlebot named BLOCK (sanity): {google_block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
