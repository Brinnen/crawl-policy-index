"""Apply curated vertical/country labels onto a panel.

Unknown is valid. Language is not assigned here — it is observed later.
Country is only set from this file, never from html lang or a TLD guess.
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


def load_labels(path: Path | None = None) -> dict[str, Any]:
    src = path or DEFAULT_LABELS
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    news: dict[str, str] = {}
    for row in data.get("news_domains") or []:
        if isinstance(row, str):
            domain, country = row.strip().lower(), ""
        else:
            domain = str(row.get("domain") or "").strip().lower()
            country = str(row.get("country") or "").strip().upper()
        if not DOMAIN_RE.match(domain):
            continue
        if country and len(country) != 2:
            country = ""
        news[domain] = country
    return {"news": news}


def apply_labels(rows: list[dict[str, str]], labels: dict[str, Any]) -> list[dict[str, str]]:
    news: dict[str, str] = labels.get("news") or {}
    if not news:
        return rows
    by_domain = {r["domain"]: r for r in rows}
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
