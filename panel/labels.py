"""Apply curated vertical/country labels onto a panel.

Unknown is valid. Language is not assigned here — it is observed later.
Country is only set from this file or a ccTLD, never from html lang.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DOMAIN_RE = re.compile(
    r"^(?:xn--[a-z0-9-]+|[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)

DEFAULT_LABELS = Path(__file__).resolve().parents[1] / "registry" / "verticals.yml"

KNOWN_VERTICALS = {
    "news",
    "social",
    "ecommerce",
    "search",
    "streaming",
    "tech",
    "travel",
    "jobs",
    "directory",
    "weather",
    "edu",
    "gov",
    "other",
}


def _country(value: object) -> str:
    country = str(value or "").strip().upper()
    if len(country) == 2 and country.isalpha():
        return country
    return ""


def _domain(value: object) -> str:
    domain = str(value or "").strip().lower()
    if DOMAIN_RE.match(domain):
        return domain
    return ""


def load_labels(path: Path | None = None) -> dict[str, Any]:
    src = path or DEFAULT_LABELS
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    news: dict[str, str] = {}
    for row in data.get("news_domains") or []:
        if isinstance(row, str):
            domain, country = _domain(row), ""
        else:
            domain = _domain((row or {}).get("domain"))
            country = _country((row or {}).get("country"))
        if domain:
            news[domain] = country
    known: dict[str, dict[str, str]] = {}
    for row in data.get("known_domains") or []:
        if not isinstance(row, dict):
            continue
        domain = _domain(row.get("domain"))
        if not domain:
            continue
        vertical = str(row.get("vertical") or "").strip().lower()
        if vertical not in KNOWN_VERTICALS:
            vertical = ""
        known[domain] = {"vertical": vertical, "country": _country(row.get("country"))}
    return {"news": news, "known": known}


def labeled_country(domain: str, labels: dict[str, Any] | None = None) -> str:
    data = labels or load_labels()
    host = (domain or "").strip().lower()
    known = (data.get("known") or {}).get(host) or {}
    if known.get("country"):
        return known["country"]
    return (data.get("news") or {}).get(host, "")


def labeled_vertical(domain: str, labels: dict[str, Any] | None = None) -> str:
    data = labels or load_labels()
    host = (domain or "").strip().lower()
    if host in (data.get("news") or {}):
        return "news"
    known = (data.get("known") or {}).get(host) or {}
    return known.get("vertical") or ""


def apply_labels(rows: list[dict[str, str]], labels: dict[str, Any]) -> list[dict[str, str]]:
    known: dict[str, dict[str, str]] = labels.get("known") or {}
    news: dict[str, str] = labels.get("news") or {}
    by_domain = {r["domain"]: r for r in rows}
    for domain, meta in known.items():
        row = by_domain.get(domain)
        if row is None:
            continue
        vertical = meta.get("vertical") or ""
        if vertical and vertical != "other":
            row["vertical"] = vertical
        if meta.get("country"):
            row["country"] = meta["country"]
    if not news:
        return rows
    for domain, country in news.items():
        row = by_domain.get(domain)
        if row is None:
            template = rows[0] if rows else {
                "psl_version": "dev-unpinned",
                "added_on": "",
            }
            row = {
                "domain": domain,
                "strata": "news",
                "tranco_rank": "",
                "country": country,
                "vertical": "news",
                "psl_version": template.get("psl_version", "dev-unpinned"),
                "added_on": template.get("added_on", ""),
            }
            rows.append(row)
            by_domain[domain] = row
            continue
        tags = [s for s in (row.get("strata") or "").split("|") if s]
        if "news" not in tags:
            tags.append("news")
        row["strata"] = "|".join(tags)
        row["vertical"] = "news"
        if country:
            row["country"] = country
    return rows
