"""Tranco top-list download. Always record the list ID; never publish 'latest'."""

from __future__ import annotations

import csv
import io
import urllib.request

UA = "CrawlPolicyIndex/1.0 (+https://github.com/Brinnen/crawl-policy-index)"


def resolve_list_id(list_id: str | None) -> str:
    if list_id and list_id != "latest":
        return list_id
    req = urllib.request.Request(
        "https://tranco-list.eu/top-1m-id",
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("ascii").strip()


def fetch_tranco(list_id: str, top_n: int) -> list[tuple[int, str]]:
    """Return (rank, domain) for the first top_n pay-level domains."""
    url = f"https://tranco-list.eu/download/{list_id}/{top_n}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    rows: list[tuple[int, str]] = []
    reader = csv.reader(io.StringIO(body))
    for rec in reader:
        if len(rec) < 2:
            continue
        try:
            rank = int(rec[0].strip())
        except ValueError:
            continue
        domain = rec[1].strip().lower().rstrip(".")
        if domain:
            rows.append((rank, domain))
    return rows
