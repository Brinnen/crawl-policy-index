"""Top-level sitemap metadata only. Never follow child sitemaps."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime

from lxml import etree

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class SitemapFact:
    present: bool
    root_element: str  # sitemapindex | urlset | invalid
    child_count: int
    lastmod_min: date | None
    lastmod_max: date | None
    lastmod_coverage: float | None


def parse(body: bytes, size_cap: int = MAX_BYTES) -> SitemapFact:
    if not body:
        return SitemapFact(False, "invalid", 0, None, None, None)
    if len(body) > size_cap:
        body = body[:size_cap]
    try:
        context = etree.iterparse(
            io.BytesIO(body),
            events=("end",),
            recover=True,
            resolve_entities=False,
            huge_tree=False,
        )
    except etree.XMLSyntaxError:
        return SitemapFact(True, "invalid", 0, None, None, None)

    root_name = None
    child_count = 0
    lastmods: list[date] = []
    try:
        for _, elem in context:
            local = _local(elem.tag)
            if local in {"urlset", "sitemapindex"} and root_name is None:
                root_name = local
            if local in {"url", "sitemap"}:
                child_count += 1
            if local == "lastmod" and elem.text:
                parsed = _parse_date(elem.text.strip())
                if parsed:
                    lastmods.append(parsed)
            elem.clear()
    except etree.XMLSyntaxError:
        return SitemapFact(True, "invalid", 0, None, None, None)

    if root_name not in {"urlset", "sitemapindex"}:
        # iterparse may miss the root if we only listen to end of children;
        # fall back to a single parse of the start.
        root_name = _peek_root(body) or "invalid"

    coverage = (len(lastmods) / child_count) if child_count else None
    return SitemapFact(
        present=True,
        root_element=root_name if root_name in {"urlset", "sitemapindex"} else "invalid",
        child_count=child_count,
        lastmod_min=min(lastmods) if lastmods else None,
        lastmod_max=max(lastmods) if lastmods else None,
        lastmod_coverage=coverage,
    )


def _peek_root(body: bytes) -> str | None:
    try:
        root = etree.fromstring(body[:65536], parser=etree.XMLParser(recover=True, resolve_entities=False))
    except etree.XMLSyntaxError:
        return None
    return _local(root.tag)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            if fmt == "%Y-%m-%d":
                return datetime.strptime(value[:10], fmt).date()
            cleaned = value.replace("Z", "+00:00") if value.endswith("Z") else value
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
