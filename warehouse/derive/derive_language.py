"""Fill language, country, and site type from html_home observations. Does not fetch."""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "parser"))
sys.path.insert(0, str(ROOT / "panel"))

from cpi_parser.category import category_from_html  # noqa: E402
from cpi_parser.html_country import country_from_html  # noqa: E402
from cpi_parser.html_lang import detect_html_language  # noqa: E402
from labels import labeled_vertical, load_labels  # noqa: E402
from warehouse.cctld import category_from_domain  # noqa: E402
from warehouse.dsn import database_dsn  # noqa: E402

UPSERT = """
INSERT INTO domain_language (
    domain, language, language_source, observed_at, content_sha256,
    http_status, panel_version, robots_allowed, category, country
) VALUES (
    %(domain)s, %(language)s, %(language_source)s, %(observed_at)s,
    %(content_sha256)s, %(http_status)s, %(panel_version)s, %(robots_allowed)s,
    %(category)s, %(country)s
)
ON CONFLICT (domain) DO UPDATE SET
    language = COALESCE(EXCLUDED.language, domain_language.language),
    language_source = CASE
      WHEN EXCLUDED.language IS NOT NULL THEN EXCLUDED.language_source
      WHEN domain_language.language IS NOT NULL THEN domain_language.language_source
      ELSE EXCLUDED.language_source
    END,
    observed_at = EXCLUDED.observed_at,
    content_sha256 = COALESCE(EXCLUDED.content_sha256, domain_language.content_sha256),
    http_status = COALESCE(EXCLUDED.http_status, domain_language.http_status),
    panel_version = EXCLUDED.panel_version,
    robots_allowed = EXCLUDED.robots_allowed,
    category = COALESCE(
      NULLIF(EXCLUDED.category, 'other'),
      NULLIF(domain_language.category, 'other'),
      EXCLUDED.category,
      domain_language.category
    ),
    country = COALESCE(
      NULLIF(EXCLUDED.country, ''),
      NULLIF(domain_language.country, ''),
      EXCLUDED.country,
      domain_language.country
    );
"""

OBS_SQL = """
SELECT DISTINCT ON (fo.domain)
    fo.domain, fo.outcome, fo.content_sha256, fo.http_status,
    fo.fetched_at, fo.panel_version, fo.error_detail
FROM fetch_observation fo
JOIN panel_domain pd
  ON pd.domain = fo.domain
 AND pd.panel_version = %s
WHERE fo.resource = 'html_home'
ORDER BY fo.domain, fo.fetched_at DESC;
"""


def _read_blob(store: Path, sha: str) -> bytes:
    path = store / "blob" / sha[0:2] / sha[2:4] / f"{sha}.gz"
    with gzip.open(path, "rb") as f:
        return f.read()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True)
    p.add_argument("--panel-version", default="sites100k")
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)
    dsn = args.dsn or database_dsn()
    store = Path(args.store)
    labels = load_labels()

    import psycopg

    assigned = 0
    unknown = 0
    skipped_robots = 0
    countries = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(OBS_SQL, (args.panel_version,))
            rows = cur.fetchall()
            for i, (domain, outcome, sha, status, fetched_at, panel_version, _err) in enumerate(
                rows, start=1
            ):
                html_cat = ""
                html_cc = ""
                body = b""
                if outcome == "ok" and sha:
                    try:
                        body = _read_blob(store, sha)
                    except FileNotFoundError:
                        body = b""
                if body:
                    html_cat = category_from_html(body)
                    html_cc = country_from_html(body)
                cat = category_from_domain(domain, labeled_vertical(domain, labels) or html_cat)
                if html_cc:
                    countries += 1
                if outcome == "skipped_robots":
                    cur.execute(
                        UPSERT,
                        {
                            "domain": domain,
                            "language": None,
                            "language_source": "robots_disallow",
                            "observed_at": fetched_at,
                            "content_sha256": None,
                            "http_status": status,
                            "panel_version": panel_version,
                            "robots_allowed": False,
                            "category": cat,
                            "country": html_cc or None,
                        },
                    )
                    skipped_robots += 1
                    unknown += 1
                else:
                    lang = None
                    source = "http_error"
                    if outcome == "ok" and body:
                        lang, source = detect_html_language(body)
                    elif outcome == "ok" and sha:
                        source = "missing"
                    elif outcome in {"not_found", "empty_body"}:
                        source = "missing"
                    cur.execute(
                        UPSERT,
                        {
                            "domain": domain,
                            "language": lang,
                            "language_source": source if lang or source != "html_lang" else "missing",
                            "observed_at": fetched_at,
                            "content_sha256": sha,
                            "http_status": status,
                            "panel_version": panel_version,
                            "robots_allowed": True,
                            "category": cat,
                            "country": html_cc or None,
                        },
                    )
                    if lang:
                        assigned += 1
                    else:
                        unknown += 1
                if i % 500 == 0:
                    conn.commit()
                if i % 10000 == 0:
                    print(f"  … language {i}", flush=True)
        conn.commit()
    print(
        f"language assigned={assigned} unknown={unknown} "
        f"robots_disallow={skipped_robots} html_country={countries} "
        f"(existing rows kept)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
