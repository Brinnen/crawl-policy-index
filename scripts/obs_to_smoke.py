"""Copy fetched robots.txt blobs into data/smoke/<domain>/robots.txt for the table."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--store", default=str(ROOT / "data" / "store"))
    p.add_argument("--out", default=str(ROOT / "data" / "smoke"))
    args = p.parse_args(argv)

    store = Path(args.store)
    out = Path(args.out)
    obs_root = store / "obs"
    if not obs_root.exists():
        print(f"No observations in {obs_root}")
        return 1

    written = 0
    for ndjson in obs_root.rglob("*.ndjson"):
        if "resource=robots_txt" not in str(ndjson).replace("\\", "/"):
            continue
        for line in ndjson.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("outcome") != "ok" or not rec.get("content_sha256"):
                continue
            sha = rec["content_sha256"]
            blob = store / "blob" / sha[0:2] / sha[2:4] / f"{sha}.gz"
            if not blob.exists():
                continue
            dest_dir = out / rec["domain"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_dir.joinpath("robots.txt").write_bytes(gzip.decompress(blob.read_bytes()))
            written += 1
    print(f"Wrote {written} robots.txt files to {out}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
