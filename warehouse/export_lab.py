"""Export lab warehouse views to the Astro tracker data file.

Called by scripts/daily-run.sh after warehouse-once.sh. Writes:

    site/tracker/src/data/lab.json

scripts/publish-lab.sh copies that file to /var/www/cpi/snapshot/lab.json
(the live numbers). The tracker fetches that URL in the browser.

The tracker does not publish this file as a download. It is a build input
and a snapshot payload.
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
JOIN panel_domain pd
  ON pd.domain = pi.domain AND pd.panel_version = %s
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
JOIN panel_domain pd
  ON pd.domain = pi.domain AND pd.panel_version = %s
GROUP BY a.slug, a.ua_token, a.display_name, a.operator, a.purpose
ORDER BY count(*) FILTER (WHERE pi.state = 'BLOCKED') DESC, a.operator, a.slug
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--dsn", default=None)
    p.add_argument("--panel-version", default="sites1000")
    args = p.parse_args(argv)
    panel = args.panel_version

    import psycopg

    dsn = args.dsn or database_dsn()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT domain_count FROM panel_version WHERE version = %s",
                (panel,),
            )
            row = cur.fetchone()
            panel_size = int(row[0]) if row else 0
            cur.execute(
                """
                SELECT count(*)
                FROM fetch_observation fo
                JOIN panel_domain pd
                  ON pd.domain = fo.domain AND pd.panel_version = %s
                WHERE fo.resource = 'robots_txt'
                """,
                (panel,),
            )
            obs = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM wildcard_interval wi
                JOIN panel_domain pd
                  ON pd.domain = wi.domain AND pd.panel_version = %s
                WHERE wi.valid_to IS NULL
                """,
                (panel,),
            )
            wild = cur.fetchone()[0]
            cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE n.state = 'BLOCKED'),
                    count(*) FILTER (WHERE n.state = 'ALLOWED'),
                    count(*) FILTER (WHERE n.state = 'PARTIAL')
                FROM v_lab_gptbot_named n
                JOIN panel_domain pd
                  ON pd.domain = n.domain AND pd.panel_version = %s
                """,
                (panel,),
            )
            named_block, named_allow, named_partial = cur.fetchone()
            cur.execute(
                """
                SELECT count(*) FILTER (WHERE named_block_rows > 0)
                FROM (
                    SELECT
                        CASE
                            WHEN n.domain = 'amazon.com' OR n.domain LIKE 'amazon.%%'
                            THEN 'amazon.com'
                            ELSE n.domain
                        END AS group_key,
                        count(*) FILTER (WHERE n.state = 'BLOCKED') AS named_block_rows
                    FROM v_lab_gptbot_named n
                    JOIN panel_domain pd
                      ON pd.domain = n.domain AND pd.panel_version = %s
                    GROUP BY 1
                ) g
                """,
                (panel,),
            )
            grouped_block = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM policy_interval gpt
                JOIN panel_domain pd
                  ON pd.domain = gpt.domain AND pd.panel_version = %s
                LEFT JOIN policy_interval search
                  ON search.domain = gpt.domain
                 AND search.valid_to IS NULL
                 AND search.agent_slug = 'openai-searchbot'
                WHERE gpt.agent_slug = 'openai-gptbot'
                  AND gpt.valid_to IS NULL
                  AND gpt.state = 'BLOCKED'
                  AND COALESCE(search.state::text, '') IS DISTINCT FROM 'BLOCKED'
                """,
                (panel,),
            )
            split = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM policy_interval pi
                JOIN panel_domain pd
                  ON pd.domain = pi.domain AND pd.panel_version = %s
                WHERE pi.agent_slug = 'google-googlebot'
                  AND pi.state = 'BLOCKED'
                  AND pi.valid_to IS NULL
                """,
                (panel,),
            )
            google_block = cur.fetchone()[0]
            cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE wi.state = 'BLOCKED'),
                    count(*) FILTER (WHERE wi.state = 'ALLOWED'),
                    count(*) FILTER (WHERE wi.state = 'PARTIAL')
                FROM wildcard_interval wi
                JOIN panel_domain pd
                  ON pd.domain = wi.domain AND pd.panel_version = %s
                WHERE wi.valid_to IS NULL
                  AND wi.has_wildcard_group
                """,
                (panel,),
            )
            wc_block, wc_allow, wc_partial = cur.fetchone()
            cur.execute(
                """
                SELECT count(*)
                FROM wildcard_interval wi
                JOIN panel_domain pd
                  ON pd.domain = wi.domain AND pd.panel_version = %s
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
                """,
                (panel,),
            )
            gptbot_blanket = cur.fetchone()[0]
            include_rows = panel_size <= 5000
            named: list[dict] = []
            blanket: list[dict] = []
            grouped: list[dict] = []
            if include_rows:
                cur.execute(NAMED_SQL, (panel,))
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
                        "kind": "named",
                        "group_key": group_key(domain),
                    }
                    for domain, state, vf, slug, token, display, operator, purpose in cur.fetchall()
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
                cur.execute(
                    """
                    SELECT wi.domain, wi.state::text, wi.valid_from::text
                    FROM wildcard_interval wi
                    JOIN panel_domain pd
                      ON pd.domain = wi.domain AND pd.panel_version = %s
                    WHERE wi.valid_to IS NULL
                      AND wi.has_wildcard_group
                      AND wi.state = 'BLOCKED'
                    ORDER BY wi.domain
                    """,
                    (panel,),
                )
                blanket = [
                    {
                        "domain": domain,
                        "state": state,
                        "valid_from": vf,
                        "agent_slug": "wildcard-star",
                        "token": "All bots (*)",
                        "agent": "All bots",
                        "operator": "Site-wide rule",
                        "purpose": "blanket",
                        "kind": "blanket",
                        "group_key": group_key(domain),
                    }
                    for domain, state, vf in cur.fetchall()
                ]
            cur.execute(BY_AGENT_SQL, (panel,))
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

    by_agent.insert(
        0,
        {
            "slug": "wildcard-star",
            "token": "All bots (*)",
            "agent": "All bots",
            "operator": "Site-wide rule",
            "purpose": "blanket",
            "named_block": wc_block,
            "named_allow": wc_allow,
            "named_partial": wc_partial,
        },
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "panel_version": panel,
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
            "gptbot_blanket_block": gptbot_blanket,
            "openai_split": split,
            "googlebot_named_block": google_block,
            "calendar_observations": obs,
            "panel_size": panel_size,
        },
        "by_agent": by_agent,
        "named": named,
        "blanket": blanket,
        "grouped": grouped,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {out} panel={panel} size={panel_size} "
        f"({len(named)} named rows, {len(blanket)} block-all-bots, {len(by_agent)} agents)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
