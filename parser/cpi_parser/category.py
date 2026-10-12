"""Site type from homepage HTML. Best-effort product filter. Unknown is valid."""

from __future__ import annotations

import re

NEWS_JSON = re.compile(
    r"NewsMediaOrganization|ReportageNewsArticle|NewsArticle",
    re.I,
)
SHOP_JSON = re.compile(
    r'"@type"\s*:\s*"?(OnlineStore|Store)"?',
    re.I,
)
EDU_JSON = re.compile(r"CollegeOrUniversity|EducationalOrganization", re.I)
GOV_JSON = re.compile(r"GovernmentOrganization", re.I)
TRAVEL_JSON = re.compile(r"LodgingBusiness|TravelAgency|Airline", re.I)
SHOP_PLATFORM = re.compile(
    r"cdn\.shopify\.com|Shopify\.theme|myshopify\.com|woocommerce|wc-ajax|"
    r"Mage\.Cookies|cdn\.bigcommerce\.com",
    re.I,
)

NEWS_WORDS = re.compile(
    r"\b(breaking news|latest news|top stories|newspaper|tidning|zeitung|"
    r"noticias|notizie|actualité|nachrichten|новини|новости|newswire)\b",
    re.I,
)
SHOP_WORDS = re.compile(
    r"\b(add to cart|add to bag|add to basket|webshop|web shop|"
    r"añadir al carrito|in den warenkorb|ajouter au panier|"
    r"toevoegen aan winkelwagen|adicionar ao carrinho)\b",
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
    if (
        SHOP_JSON.search(text)
        or SHOP_PLATFORM.search(text)
        or SHOP_WORDS.search(text)
    ):
        return "ecommerce"
    if TRAVEL_JSON.search(text):
        return "travel"
    return "other"
