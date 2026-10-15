#!/usr/bin/env python3
"""Write panel-sites1m-queue.csv: 1M names that still have no robots.txt in the store."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def robots_done(store: Path) -> set[str]:
    done: set[str] = set()
    root = store / "obs"
    if not root.exists():
        return done
    for path in root.rglob("*.ndjson"):
        if "resource=robots_txt" not in path.as_posix():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                domain = (row.get("domain") or "").strip().lower()
                if domain:
                    done.add(domain)
    return done


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--panel", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    panel = Path(args.panel)
    if not panel.exists():
        print(f"missing panel {panel}", file=sys.stderr)
        return 1
    with panel.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "domain" not in reader.fieldnames:
            print("panel CSV needs a domain column", file=sys.stderr)
            return 1
        fields = list(reader.fieldnames)
        rows = list(reader)
    have = robots_done(Path(args.store))
    leftover = [row for row in rows if (row.get("domain") or "").strip().lower() not in have]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(leftover)
    print(
        f"queue {len(leftover)} remaining "
        f"({len(have)} already have robots, panel {len(rows)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
