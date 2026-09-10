"""Fetch robots.txt for a small real panel. No compile step."""

from __future__ import annotations

import argparse
import csv
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UA = "CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)"
ALL_RESOURCES = (
    ("robots.txt", "robots.txt"),
    ("llms.txt", "llms.txt"),
    ("sitemap.xml", "sitemap.xml"),
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--panel", default=str(ROOT / "data" / "panel-mini.csv"))
    p.add_argument("--out", default=str(ROOT / "data" / "smoke"))
    p.add_argument("--all-files", action="store_true", help="also fetch llms.txt and sitemap.xml")
    args = p.parse_args(argv)

    panel = Path(args.panel)
    out = Path(args.out)
    resources = ALL_RESOURCES if args.all_files else (("robots.txt", "robots.txt"),)

    domains = []
    with panel.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            d = row["domain"].strip()
            if d:
                domains.append(d)

    out.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    ok = missing = failed = 0
    robots_ok = 0

    print(f"Fetching {len(domains)} sites ({len(resources)} file(s) each). This can take a few minutes.")
    for domain in domains:
        dest = out / domain
        dest.mkdir(parents=True, exist_ok=True)
        for name, filename in resources:
            url = f"https://{domain}/{name}"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                    body = resp.read()
                (dest / filename).write_bytes(body)
                print(f"  {domain}/{name}: saved ({len(body)} bytes)")
                ok += 1
                if filename == "robots.txt" and body:
                    robots_ok += 1
            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    print(f"  {domain}/{name}: not found")
                    missing += 1
                else:
                    print(f"  {domain}/{name}: HTTP {e.code}")
                    failed += 1
            except Exception as e:
                print(f"  {domain}/{name}: {e}")
                failed += 1

    print("")
    print(f"Finished. saved={ok}  not_found={missing}  failed={failed}  robots.txt kept={robots_ok}")
    print(f"Files are in: {out}")
    if robots_ok == 0:
        print("No robots.txt files were saved. Stop here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
