"""Skip Tranco names that are CDNs, DNS, or object storage — not websites."""

from __future__ import annotations

from pathlib import Path

_DENYLIST_PATH = Path(__file__).with_name("infra_denylist.txt")
_cached: frozenset[str] | None = None
# Product hostnames that are not subdomains of the listed suffix.
_HYPHEN_ENDINGS = ("-msedge.net", "-azurefd.net", "-cdn.net", "-cdn.com", "-cdn.ru")


def load_suffixes(path: Path | None = None) -> frozenset[str]:
    global _cached
    src = path or _DENYLIST_PATH
    if path is None and _cached is not None:
        return _cached
    suffixes: set[str] = set()
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip().lower().rstrip(".")
        if line:
            suffixes.add(line)
    frozen = frozenset(suffixes)
    if path is None:
        _cached = frozen
    return frozen


def is_infrastructure(domain: str, suffixes: frozenset[str] | None = None) -> bool:
    host = domain.lower().rstrip(".")
    if not host:
        return False
    table = suffixes if suffixes is not None else load_suffixes()
    labels = host.split(".")
    for i in range(len(labels) - 1):
        if ".".join(labels[i:]) in table:
            return True
    if any(host.endswith(end) for end in _HYPHEN_ENDINGS):
        return True
    # tiktokcdn-eu.com, namebrightdns.com, b-cdn.net — not a website.
    for label in labels[:-1]:
        if "cdn" in label or "dns" in label:
            return True
    return False
