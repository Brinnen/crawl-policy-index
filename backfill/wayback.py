"""Internet Archive reconstruction. 1 req/s, single worker. Do not raise the rate."""

from __future__ import annotations

CDX = "https://web.archive.org/cdx/search/cdx"
RATE_LIMIT_RPS = 1.0


def cdx_query(domain: str, from_date: str = "20220101") -> str:
    return (
        f"{CDX}?url={domain}/robots.txt&output=json"
        f"&fl=timestamp,digest,statuscode,length,mimetype"
        f"&filter=statuscode:200&collapse=digest&from={from_date}"
    )


def original_bytes_url(timestamp: str, domain: str) -> str:
    # id_ returns original bytes. Omitting it returns Wayback chrome and
    # will silently poison the parser.
    return f"https://web.archive.org/web/{timestamp}id_/http://{domain}/robots.txt"
