"""One-shot homepage fetch for the public 100-site sample.

Fetches "/" even when robots.txt would say no. Does not spoof Googlebot.
Language comes from the page. Country stays labeled or ccTLD — never html lang.
"""

from __future__ import annotations

import gzip
import json
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "parser"))
sys.path.insert(0, str(ROOT / "panel"))

from cpi_parser.category import category_from_html  # noqa: E402
from cpi_parser.html_lang import detect_html_language  # noqa: E402
from labels import labeled_country, labeled_vertical  # noqa: E402
from warehouse.cctld import category_from_domain, country_from_domain  # noqa: E402

UA = "CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)"
CAP = 524288
TIMEOUT = 15
WORKERS = 8
PREVIEW = ROOT / "site" / "tracker" / "src" / "data" / "preview.json"
HOSTS = ROOT / "warehouse" / "showcase_hosts.txt"

CTX = ssl.create_default_context()


def _get(url: str, accept: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "en",
            "Accept-Encoding": "gzip",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read(CAP + 1)
            if len(raw) > CAP:
                raw = raw[:CAP]
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if "gzip" in enc or (len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B):
                try:
                    raw = gzip.decompress(raw)[: CAP * 4]
                except OSError:
                    pass
            return int(resp.status), raw, resp.headers.get("Content-Language") or ""
    except urllib.error.HTTPError as err:
        body = err.read(CAP) if err.fp else b""
        return int(err.code), body, ""
    except Exception:
        return 0, b"", ""


def fetch_bytes(domain: str, path: str, accept: str) -> tuple[int, bytes, str]:
    status, body, lang = _get(f"https://{domain}{path}", accept)
    if status:
        return status, body, lang
    return _get(f"http://{domain}{path}", accept)


def enrich_one(domain: str) -> tuple[str, str, str, str, str]:
    labeled = labeled_vertical(domain)
    country = labeled_country(domain) or country_from_domain(domain)
    category = category_from_domain(domain, labeled)
    language = ""
    st, html, content_language = fetch_bytes(
        domain, "/", "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
    )
    if not html or st >= 400 or st == 0:
        return domain, language, country, category, f"http_{st or 'fail'}"
    lang, _source = detect_html_language(html, content_language or None)
    if lang:
        language = lang
    if not labeled:
        category = category_from_domain(domain, category_from_html(html))
    return domain, language, country, category, "ok"


def main() -> int:
    hosts = [line.strip() for line in HOSTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    pack = json.loads(PREVIEW.read_text(encoding="utf-8"))
    by_host = {row[0]: list(row) for row in pack.get("sites") or []}
    ok = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(enrich_one, host): host for host in hosts}
        for fut in as_completed(futs):
            domain, language, country, category, note = fut.result()
            prev = by_host.get(domain, [domain, "", "", ""])
            if note == "ok":
                by_host[domain] = [domain, language or prev[1], country, category or "other"]
                ok += 1
            else:
                by_host[domain] = [
                    domain,
                    language or prev[1],
                    country or prev[2],
                    category if category and category != "other" else (prev[3] or category or "other"),
                ]
                failed += 1
            print(f"{domain:24} {by_host[domain][1] or '—':5} {country or '—':4} {by_host[domain][3]:12} {note}")
    pack["sites"] = [by_host.get(h, [h, "", "", ""]) for h in hosts]
    PREVIEW.write_text(json.dumps(pack, separators=(",", ":")) + "\n", encoding="utf-8")
    langs = sum(1 for row in pack["sites"] if row[1])
    countries = sum(1 for row in pack["sites"] if row[2])
    typed = sum(1 for row in pack["sites"] if row[3] and row[3] != "other")
    print(
        f"wrote {PREVIEW} ok={ok} failed={failed} "
        f"language={langs} country={countries} typed={typed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
