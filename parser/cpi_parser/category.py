"""Rough site category from homepage HTML. Best-effort product filter."""

from __future__ import annotations

import re

NEWS_JSON = re.compile(
    r"NewsMediaOrganization|NewsArticle|ReportageNewsArticle",
    re.I,
)
SHOP_JSON = re.compile(r"OnlineStore", re.I)
EDU_JSON = re.compile(r"CollegeOrUniversity|EducationalOrganization", re.I)
GOV_JSON = re.compile(r"GovernmentOrganization", re.I)

NEWS_WORDS = re.compile(
    r"\b(breaking news|latest news|newspaper|nyheter|tidning|zeitung|"
    r"noticias|newsroom|newswire)\b",
    re.I,
)
SHOP_WORDS = re.compile(
    r"\b(add to cart|shopping cart|checkout|webshop|web shop|online store|buy now)\b",
    re.I,
)
EDU_WORDS = re.compile(
    r"\b(university|universitet|universidad|université|college|campus)\b",
    re.I,
)
GOV_WORDS = re.compile(
    r"\b(government|regering|regeringen|ministerium|ministry of|kommun)\b",
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
