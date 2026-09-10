#!/usr/bin/env python3
"""Build a frozen, versioned panel CSV.

    python panel/build_panel.py --version tranco1000 --tranco-top 1000 --tranco-id 94XL2
    python panel/build_panel.py --version dev --sample 5000 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources.tranco import fetch_tranco, resolve_list_id

DOMAIN_RE = re.compile(
    r"^(?:xn--[a-z0-9-]+|[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
PSL_VERSION_DEV = "dev-unpinned"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tranco-top", type=int, default=0)
    p.add_argument(
        "--tranco-id",
        default="94XL2",
        help="Pinned Tranco list ID. Never publish a panel built from an unrecorded 'latest'.",
    )
    p.add_argument("--out-dir", default="data")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    added_on = datetime.now(timezone.utc).date().isoformat()

    tranco_list_id = "none-dev-sample"
    sources: list[dict] = []
    psl = PSL_VERSION_DEV

    if args.tranco_top:
        tranco_list_id = resolve_list_id(args.tranco_id)
        ranked = fetch_tranco(tranco_list_id, args.tranco_top)
        rows = _from_tranco(ranked, added_on)
        sources = [
            {
                "name": "tranco",
                "url": f"https://tranco-list.eu/download/{tranco_list_id}/{args.tranco_top}",
                "retrieved_on": added_on,
                "list_id": tranco_list_id,
                "note": "Pay-level domains, top N of a pinned Tranco list. Not the full published panel.",
            }
        ]
    elif args.sample:
        rows = _synthetic_sample(args.sample, args.seed, added_on)
        sources = [
            {
                "name": "synthetic-dev",
                "url": None,
                "retrieved_on": added_on,
                "note": "Deterministic sample for local development. Not a published panel.",
            }
        ]
    else:
        raise SystemExit("Pass --tranco-top N (pinned list) or --sample N (synthetic).")

    name = f"panel-{args.version}.csv"
    path = out_dir / name
    fieldnames = [
        "domain",
        "strata",
        "tranco_rank",
        "country",
        "vertical",
        "psl_version",
        "added_on",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "version": args.version,
        "frozen_on": added_on,
        "psl_version": psl,
        "tranco_list_id": tranco_list_id,
        "rng_seed": args.seed,
        "domain_count": len(rows),
        "checksum_sha256": digest,
        "sources": sources,
    }
    man_path = out_dir / f"panel-{args.version}.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(rows)} domains, list={tranco_list_id}, sha256={digest})")
    return 0


def _from_tranco(ranked: list[tuple[int, str]], added_on: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    skipped = 0
    for rank, domain in ranked:
        try:
            domain = domain.encode("idna").decode("ascii")
        except UnicodeError:
            skipped += 1
            continue
        if not DOMAIN_RE.match(domain) or domain in seen:
            skipped += 1
            continue
        seen.add(domain)
        rows.append(
            {
                "domain": domain,
                "strata": "head",
                "tranco_rank": str(rank),
                "country": "",
                "vertical": "other",
                "psl_version": PSL_VERSION_DEV,
                "added_on": added_on,
            }
        )
    if skipped:
        print(f"skipped {skipped} invalid or duplicate domains")
    if not rows:
        raise RuntimeError("Tranco download produced zero valid domains")
    return rows


def _synthetic_sample(n: int, seed: int, added_on: str) -> list[dict[str, str]]:
    rng = random.Random(seed)
    pool = [f"d{i:05d}.example" for i in range(100_000)]
    chosen = rng.sample(pool, n)
    rows = []
    for domain in chosen:
        if not DOMAIN_RE.match(domain):
            raise RuntimeError(f"invalid domain {domain}")
        rows.append(
            {
                "domain": domain,
                "strata": "tail",
                "tranco_rank": "",
                "country": "",
                "vertical": "other",
                "psl_version": PSL_VERSION_DEV,
                "added_on": added_on,
            }
        )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
