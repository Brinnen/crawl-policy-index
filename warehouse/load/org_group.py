"""Map related ccTLDs to one group key for lab rollups. Not a published figure."""

from __future__ import annotations


def group_key(domain: str) -> str:
    host = domain.lower().rstrip(".")
    if host == "amazon.com" or host.startswith("amazon."):
        return "amazon.com"
    return host
