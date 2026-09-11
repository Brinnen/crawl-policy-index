"""COPY-ish load of fetcher NDJSON observations + blob inventory.

Skips lab run_dates that are not calendar dates (e.g. 2026-09-10-sites).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from warehouse.dsn import database_dsn  # noqa: E402

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

UPSERT_OBS = """
INSERT INTO fetch_observation (
    domain, resource, run_date, prov, fetched_at, url_requested, url_final,
    redirect_count, crossed_reg_domain, scheme_used, http_status, outcome,
    content_sha256, content_length, content_type, truncated, latency_ms,
    fetcher_version, panel_version, error_detail
) VALUES (
    %(domain)s, %(resource)s, %(run_date)s, 'live', %(fetched_at)s,
    %(url_requested)s, %(url_final)s, %(redirect_count)s, %(crossed_reg_domain)s,
    %(scheme_used)s, %(http_status)s, %(outcome)s, %(content_sha256)s,
    %(content_length)s, %(content_type)s, %(truncated)s, %(latency_ms)s,
    %(fetcher_version)s, %(panel_version)s, %(error_detail)s
)
ON CONFLICT (domain, resource, run_date, prov) DO NOTHING;
"""

UPSERT_BLOB = """
INSERT INTO content_blob (
    sha256, resource, byte_len, storage_key, first_seen_on, last_seen_on, seen_count
) VALUES (
    %(sha256)s, %(resource)s, %(byte_len)s, %(storage_key)s,
    %(seen_on)s, %(seen_on)s, 1
)
ON CONFLICT (sha256) DO UPDATE SET
    last_seen_on = GREATEST(content_blob.last_seen_on, EXCLUDED.last_seen_on),
    seen_count = content_blob.seen_count + 1;
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--store", required=True)
    p.add_argument("--dsn", default=None)
    args = p.parse_args(argv)
    dsn = args.dsn or database_dsn()
    store = Path(args.store)
    obs_root = store / "obs"
    if not obs_root.exists():
        print(f"no observations in {obs_root}", file=sys.stderr)
        return 1

    loaded = 0
    skipped_date = 0
    blobs: dict[str, dict] = {}

    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for ndjson in sorted(obs_root.rglob("*.ndjson")):
                if "/manifest/" in str(ndjson).replace("\\", "/"):
                    continue
                for line in ndjson.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    run_date = str(rec.get("run_date") or "")
                    if not DATE_RE.match(run_date):
                        skipped_date += 1
                        continue
                    sha = rec.get("content_sha256") or None
                    row = {
                        "domain": rec["domain"],
                        "resource": rec["resource"],
                        "run_date": run_date,
                        "fetched_at": rec.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
                        "url_requested": rec.get("url_requested") or "",
                        "url_final": rec.get("url_final") or None,
                        "redirect_count": int(rec.get("redirect_count") or 0),
                        "crossed_reg_domain": bool(rec.get("crossed_registrable_domain")),
                        "scheme_used": rec.get("scheme_used") or None,
                        "http_status": rec.get("http_status"),
                        "outcome": rec["outcome"],
                        "content_sha256": sha,
                        "content_length": int(rec.get("content_length") or 0),
                        "content_type": rec.get("content_type") or None,
                        "truncated": bool(rec.get("truncated")),
                        "latency_ms": rec.get("latency_ms"),
                        "fetcher_version": rec.get("fetcher_version") or "unknown",
                        "panel_version": rec.get("panel_version") or "unknown",
                        "error_detail": rec.get("error_detail"),
                    }
                    cur.execute(UPSERT_OBS, row)
                    loaded += 1
                    if sha:
                        key = f"blob/{sha[0:2]}/{sha[2:4]}/{sha}.gz"
                        blob_path = store / "blob" / sha[0:2] / sha[2:4] / f"{sha}.gz"
                        byte_len = int(rec.get("content_length") or 0)
                        if blob_path.exists() and byte_len <= 0:
                            byte_len = blob_path.stat().st_size
                        blobs[sha] = {
                            "sha256": sha,
                            "resource": rec["resource"],
                            "byte_len": byte_len or 0,
                            "storage_key": key,
                            "seen_on": run_date,
                        }
            for blob in blobs.values():
                cur.execute(UPSERT_BLOB, blob)
        conn.commit()
    print(
        f"loaded {loaded} calendar observations, "
        f"{len(blobs)} blobs, skipped {skipped_date} non-date run_dates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
