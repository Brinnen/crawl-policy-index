"""Rough site category from homepage HTML. Best-effort product filter."""

from __future__ import annotations

import re

NEWS_JSON = re.compile(
    r"NewsMediaOrganization|ReportageNewsArticle",
    re.I,
)
SHOP_JSON = re.compile(r'"@type"\s*:\s*"OnlineStore"', re.I)
EDU_JSON = re.compile(r"CollegeOrUniversity", re.I)
GOV_JSON = re.compile(r"GovernmentOrganization", re.I)

NEWS_WORDS = re.compile(
    r"\b(breaking news|newspaper|tidning|zeitung|noticias|newswire)\b",
    re.I,
)
SHOP_WORDS = re.compile(
    r"\b(add to cart|webshop|web shop)\b",
    re.I,
)
EDU_WORDS = re.compile(
    r"\b(university of|universitet|universidad|université)\b",
    re.I,
)
GOV_WORDS = re.compile(
    r"\b(regeringen|ministerium|ministry of)\b",
    re.I,
)


def category_from_html(body: bytes | str) -> str:
    if isinstance(body, bytes):
        text = body[:80_000].decode("utf-8", errors="replace")
    else:
        text = body[:80_000]
    if NEWS_JSON.search(text) or NEWS_WORDS.search(text):
        return "news"
    if GOV_JSON.search(text) or GOV_WORDS.search(text):
        return "gov"
    if EDU_JSON.search(text) or EDU_WORDS.search(text):
        return "edu"
    if SHOP_JSON.search(text) or SHOP_WORDS.search(text):
        return "ecommerce"
    return "other"
