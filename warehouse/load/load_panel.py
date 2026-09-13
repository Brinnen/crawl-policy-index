"""Load a frozen panel CSV + manifest into panel_version / panel_domain."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from warehouse.dsn import database_dsn  # noqa: E402

UPSERT_VERSION = """
INSERT INTO panel_version (
    version, frozen_on, psl_version, tranco_list_id, rng_seed,
    domain_count, manifest, checksum_sha256
) VALUES (
    %(version)s, %(frozen_on)s, %(psl_version)s, %(tranco_list_id)s, %(rng_seed)s,
    %(domain_count)s, %(manifest)s::jsonb, %(checksum_sha256)s
)
ON CONFLICT (version) DO UPDATE SET
    frozen_on = EXCLUDED.frozen_on,
    psl_version = EXCLUDED.psl_version,
    tranco_list_id = EXCLUDED.tranco_list_id,
    rng_seed = EXCLUDED.rng_seed,
    domain_count = EXCLUDED.domain_count,
    manifest = EXCLUDED.manifest,
    checksum_sha256 = EXCLUDED.checksum_sha256;
"""

UPSERT_DOMAIN = """
INSERT INTO panel_domain (
    panel_version, domain, strata, tranco_rank, country, vertical, added_on
) VALUES (
    %(panel_version)s, %(domain)s, %(strata)s, %(tranco_rank)s,
    %(country)s, %(vertical)s, %(added_on)s
)
ON CONFLICT (panel_version, domain) DO UPDATE SET
    strata = EXCLUDED.strata,
    tranco_rank = EXCLUDED.tranco_rank,
    country = EXCLUDED.country,
    vertical = EXCLUDED.vertical,
    added_on = EXCLUDED.added_on;
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)
    dsn = args.dsn or database_dsn()

    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    rows = []
    with Path(args.csv).open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            country = (rec.get("country") or "").strip()
            rank = (rec.get("tranco_rank") or "").strip()
            strata = [s for s in (rec.get("strata") or "head").split("|") if s]
            rows.append(
                {
                    "panel_version": man["version"],
                    "domain": rec["domain"].strip().lower(),
                    "strata": strata,
                    "tranco_rank": int(rank) if rank else None,
                    "country": country if len(country) == 2 else None,
                    "vertical": rec.get("vertical") or "other",
                    "added_on": rec.get("added_on") or man.get("frozen_on"),
                }
            )

    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                UPSERT_VERSION,
                {
                    "version": man["version"],
                    "frozen_on": man.get("frozen_on"),
                    "psl_version": man.get("psl_version") or "dev-unpinned",
                    "tranco_list_id": man.get("tranco_list_id") or "none",
                    "rng_seed": int(man.get("rng_seed") or 0),
                    "domain_count": len(rows),
                    "manifest": json.dumps(man),
                    "checksum_sha256": man.get("checksum_sha256") or "",
                },
            )
            batch = 2000
            for i in range(0, len(rows), batch):
                cur.executemany(UPSERT_DOMAIN, rows[i : i + batch])
                if i and i % 20000 == 0:
                    print(f"  … {i} / {len(rows)} domains")
        conn.commit()
    print(f"loaded panel {man['version']} ({len(rows)} domains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
