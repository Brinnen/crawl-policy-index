"""Derive wildcard_interval + explicit policy_interval from robots.txt blobs.

Idempotent for the same (domain, sha, parse_version). Calendar dates only.
"""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "parser"))

from cpi_parser import __version__ as PARSE_VERSION  # noqa: E402
from cpi_parser.detect import classify  # noqa: E402
from cpi_parser.registry import load_agents  # noqa: E402
from cpi_parser.robots import parse as parse_robots  # noqa: E402
from cpi_parser.state import RuleSource, derive_agent, derive_wildcard  # noqa: E402
from warehouse.dsn import database_dsn  # noqa: E402

OBS_SQL = """
SELECT fo.domain, fo.run_date, fo.content_sha256, fo.outcome, fo.content_type
FROM fetch_observation fo
JOIN panel_domain pd
  ON pd.domain = fo.domain
 AND pd.panel_version = %s
WHERE fo.resource = 'robots_txt'
ORDER BY fo.domain, fo.run_date;
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True)
    p.add_argument("--registry", default=str(ROOT / "registry" / "agents.yml"))
    p.add_argument("--panel-version", default="sites1000")
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)
    dsn = args.dsn or database_dsn()
    store = Path(args.store)
    agents = load_agents(args.registry)
    tokens = [(a.slug, a.ua_token) for a in agents]

    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(OBS_SQL, (args.panel_version,))
            rows = cur.fetchall()
        by_domain: dict[str, list] = {}
        shas: set[str] = set()
        for domain, run_date, sha, outcome, ctype in rows:
            by_domain.setdefault(domain, []).append((run_date, sha, outcome, ctype))
            if sha:
                shas.add(sha)

        parsed_cache: dict[str, dict] = {}
        with conn.cursor() as cur:
            for sha in shas:
                try:
                    parsed_cache[sha] = _parse_blob(cur, store, sha)
                except Exception as exc:
                    print(f"WARNING: blob {sha[:12]} parse failed: {exc}", file=sys.stderr)
                    parsed_cache[sha] = {"verdict": "empty", "body": b""}

        domains = 0
        failed = 0
        with conn.cursor() as cur:
            for domain, series in by_domain.items():
                cur.execute("SAVEPOINT derive_domain")
                try:
                    _derive_domain(cur, domain, series, parsed_cache, tokens)
                    cur.execute("RELEASE SAVEPOINT derive_domain")
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT derive_domain")
                    failed += 1
                    print(f"WARNING: derive skipped {domain}: {exc}", file=sys.stderr)
                domains += 1
                if domains % 10000 == 0:
                    print(f"  … derived {domains} / {len(by_domain)}")
        conn.commit()
    print(
        f"derived {domains} domains ({failed} skipped) at parse_version={PARSE_VERSION}"
    )
    return 0


def _blob_path(store: Path, sha: str) -> Path:
    return store / "blob" / sha[0:2] / sha[2:4] / f"{sha}.gz"


def _parse_blob(cur, store: Path, sha: str) -> dict:
    path = _blob_path(store, sha)
    if not path.exists():
        return {"verdict": "empty", "body": b""}
    body = gzip.decompress(path.read_bytes())
    verdict = str(classify(body))
    cur.execute(
        """
        UPDATE content_blob
        SET detect_result = %s, parse_version = %s, parsed_at = now(), parse_error = NULL
        WHERE sha256 = %s
        """,
        (verdict, PARSE_VERSION, sha),
    )
    out: dict = {"verdict": verdict, "body": body}
    if verdict == "robots":
        parsed = parse_robots(body)
        wc_state, has_wc = derive_wildcard(parsed)
        out["parsed"] = parsed
        out["wc_state"] = str(wc_state)
        out["has_wc"] = has_wc
    return out


def _derive_domain(cur, domain: str, series: list, cache: dict, tokens: list[tuple[str, str]]) -> None:
    prev_sha = None
    for run_date, sha, outcome, _ctype in series:
        if outcome != "ok" or not sha:
            continue
        if sha == prev_sha:
            continue
        prev_sha = sha
        info = cache.get(sha) or {"verdict": "empty"}
        if info.get("verdict") != "robots":
            _exclude(cur, domain, run_date, info.get("verdict") or "empty", sha)
            _close_all(cur, domain, run_date, sha, kind="file_removed")
            continue
        parsed = info["parsed"]
        explicit = {}
        for slug, token in tokens:
            pol = derive_agent(parsed, token)
            if pol.rule_source == RuleSource.EXPLICIT:
                explicit[slug] = pol
        _apply_wildcard(cur, domain, run_date, sha, info["wc_state"], info["has_wc"])
        _apply_explicit(cur, domain, run_date, sha, explicit)


def _exclude(cur, domain, as_of, verdict, sha) -> None:
    cur.execute(
        """
        INSERT INTO excluded_observation (domain, as_of, resource, verdict, content_sha256)
        VALUES (%s, %s, 'robots_txt', %s, %s)
        ON CONFLICT (domain, as_of, resource) DO UPDATE SET
            verdict = EXCLUDED.verdict,
            content_sha256 = EXCLUDED.content_sha256
        """,
        (domain, as_of, verdict, sha),
    )


def _close_all(cur, domain, as_of, sha, kind: str) -> None:
    cur.execute(
        """
        UPDATE wildcard_interval SET valid_to = %s
        WHERE domain = %s AND prov = 'live' AND valid_to IS NULL AND valid_from < %s
        RETURNING state, content_sha256
        """,
        (as_of, domain, as_of),
    )
    closed = cur.fetchone()
    if closed:
        _event(cur, domain, None, as_of, kind, closed[0], None, closed[1], sha)
    cur.execute(
        """
        UPDATE policy_interval SET valid_to = %s
        WHERE domain = %s AND prov = 'live' AND valid_to IS NULL AND valid_from < %s
        """,
        (as_of, domain, as_of),
    )


def _apply_wildcard(cur, domain, as_of, sha, state: str, has_wc: bool) -> None:
    cur.execute(
        """
        SELECT id, state, has_wildcard_group, content_sha256, valid_from
        FROM wildcard_interval
        WHERE domain = %s AND prov = 'live' AND valid_to IS NULL
        """,
        (domain,),
    )
    open_row = cur.fetchone()
    if open_row is None:
        cur.execute(
            """
            INSERT INTO wildcard_interval (
                domain, valid_from, valid_to, state, has_wildcard_group,
                content_sha256, parse_version, prov
            ) VALUES (%s, %s, NULL, %s, %s, %s, %s, 'live')
            """,
            (domain, as_of, state, has_wc, sha, PARSE_VERSION),
        )
        _event(cur, domain, None, as_of, "file_appeared", None, state, None, sha)
        return
    _id, old_state, old_has, old_sha, valid_from = open_row
    if old_state == state and bool(old_has) == bool(has_wc):
        if old_sha != sha:
            cur.execute(
                "UPDATE wildcard_interval SET content_sha256 = %s, parse_version = %s WHERE id = %s",
                (sha, PARSE_VERSION, _id),
            )
        return
    if valid_from >= as_of:
        return
    cur.execute("UPDATE wildcard_interval SET valid_to = %s WHERE id = %s", (as_of, _id))
    cur.execute(
        """
        INSERT INTO wildcard_interval (
            domain, valid_from, valid_to, state, has_wildcard_group,
            content_sha256, parse_version, prov
        ) VALUES (%s, %s, NULL, %s, %s, %s, %s, 'live')
        """,
        (domain, as_of, state, has_wc, sha, PARSE_VERSION),
    )
    _event(cur, domain, None, as_of, _transition(old_state, state), old_state, state, old_sha, sha)


def _apply_explicit(cur, domain, as_of, sha, desired: dict) -> None:
    cur.execute(
        """
        SELECT id, agent_slug, state, content_sha256, valid_from, matched_ua_token
        FROM policy_interval
        WHERE domain = %s AND prov = 'live' AND valid_to IS NULL
        """,
        (domain,),
    )
    open_rows = {row[1]: row for row in cur.fetchall()}
    for slug, row in list(open_rows.items()):
        if slug not in desired:
            if row[4] >= as_of:
                continue
            cur.execute("UPDATE policy_interval SET valid_to = %s WHERE id = %s", (as_of, row[0]))
            _event(cur, domain, slug, as_of, "agent_unnamed", row[2], None, row[3], sha)
    for slug, pol in desired.items():
        state = str(pol.state)
        token = pol.matched_ua_token
        delay = _crawl_delay_column(pol.crawl_delay_s)
        if slug not in open_rows:
            cur.execute(
                """
                INSERT INTO policy_interval (
                    domain, agent_slug, valid_from, valid_to, state, matched_ua_token,
                    crawl_delay_s, content_sha256, parse_version, prov
                ) VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, 'live')
                """,
                (domain, slug, as_of, state, token, delay, sha, PARSE_VERSION),
            )
            _event(cur, domain, slug, as_of, "first_seen", None, state, None, sha)
            _event(cur, domain, slug, as_of, "agent_named", None, state, None, sha)
            if state == "BLOCKED":
                _event(cur, domain, slug, as_of, "blocked", None, state, None, sha)
            continue
        row = open_rows[slug]
        if row[2] == state:
            if row[3] != sha:
                cur.execute(
                    """
                    UPDATE policy_interval
                    SET content_sha256 = %s, parse_version = %s, matched_ua_token = %s, crawl_delay_s = %s
                    WHERE id = %s
                    """,
                    (sha, PARSE_VERSION, token, delay, row[0]),
                )
            continue
        if row[4] >= as_of:
            continue
        cur.execute("UPDATE policy_interval SET valid_to = %s WHERE id = %s", (as_of, row[0]))
        cur.execute(
            """
            INSERT INTO policy_interval (
                domain, agent_slug, valid_from, valid_to, state, matched_ua_token,
                crawl_delay_s, content_sha256, parse_version, prov
            ) VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, 'live')
            """,
            (domain, slug, as_of, state, token, delay, sha, PARSE_VERSION),
        )
        kind = _transition(row[2], state)
        _event(cur, domain, slug, as_of, kind, row[2], state, row[3], sha)


def _crawl_delay_column(value: float | None) -> float | None:
    """Fit Crawl-delay into policy_interval.crawl_delay_s numeric(8,2).

    Junk values (1e12, NaN, negative) are stored as NULL. The named
    allow/block/partial still counts.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")) or number < 0:
        return None
    if number > 999_999.99:
        return None
    return round(number, 2)


def _transition(old: str, new: str) -> str:
    rank = {"ALLOWED": 0, "PARTIAL": 1, "BLOCKED": 2}
    if old == "BLOCKED" and new != "BLOCKED":
        return "unblocked"
    if new == "BLOCKED" and old != "BLOCKED":
        return "blocked"
    if rank.get(new, 0) > rank.get(old, 0):
        return "tightened"
    if rank.get(new, 0) < rank.get(old, 0):
        return "loosened"
    return "tightened"


def _event(cur, domain, agent, occurred, kind, prev_state, new_state, sha_before, sha_after) -> None:
    cur.execute(
        """
        INSERT INTO policy_event (
            domain, agent_slug, occurred_on, detected_on, kind,
            prev_state, new_state, sha256_before, sha256_after, prov
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'live')
        """,
        (domain, agent, occurred, occurred, kind, prev_state, new_state, sha_before, sha_after),
    )


if __name__ == "__main__":
    raise SystemExit(main())
