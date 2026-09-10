#!/usr/bin/env python3
"""Build a frozen, versioned panel CSV.

Dev usage (deterministic, no network):

    python panel/build_panel.py --version dev --sample 5000 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from pathlib import Path

DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PSL_VERSION_DEV = "dev-unpinned"
ADDED_ON = "2026-09-08"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="data")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.sample:
        rows = _synthetic_sample(args.sample, args.seed)
        psl = PSL_VERSION_DEV
    else:
        raise SystemExit(
            "Full panel construction (Tranco + CT + zones + news YAML) is WP0. "
            "Pass --sample N for a deterministic development panel."
        )

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
        "frozen_on": ADDED_ON,
        "psl_version": psl,
        "tranco_list_id": "none-dev-sample",
        "rng_seed": args.seed,
        "domain_count": len(rows),
        "checksum_sha256": digest,
        "sources": [
            {
                "name": "synthetic-dev",
                "url": None,
                "retrieved_on": ADDED_ON,
                "note": "Deterministic sample for local development. Not a published panel.",
            }
        ],
    }
    man_path = out_dir / f"panel-{args.version}.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(rows)} domains, sha256={digest})")
    return 0


def _synthetic_sample(n: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    pool = [f"d{i:05d}.example" for i in range(100_000)]
    chosen = rng.sample(pool, n)
    rows = []
    for i, domain in enumerate(chosen):
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
                "added_on": ADDED_ON,
            }
        )
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
