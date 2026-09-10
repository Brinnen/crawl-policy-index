from __future__ import annotations

from cpi_parser.llmstxt import parse as parse_llms
from cpi_parser.sitemap import parse as parse_sitemap


def test_urlset_children_and_lastmod():
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc><lastmod>2024-01-01</lastmod></url>
  <url><loc>https://example.com/a</loc></url>
</urlset>
"""
    fact = parse_sitemap(body)
    assert fact.root_element == "urlset"
    assert fact.child_count == 2
    assert fact.lastmod_min.isoformat() == "2024-01-01"
    assert fact.lastmod_coverage == 0.5


def test_sitemapindex_not_expanded():
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/a.xml</loc></sitemap>
  <sitemap><loc>https://example.com/b.xml</loc></sitemap>
</sitemapindex>
"""
    fact = parse_sitemap(body)
    assert fact.root_element == "sitemapindex"
    assert fact.child_count == 2


def test_invalid_xml():
    fact = parse_sitemap(b"<not-a-sitemap")
    assert fact.root_element == "invalid"


def test_llms_markdown_h1_and_links():
    body = b"# Example\n\n> comment\n\n- [Home](https://other.com/)\n- [Local](/about)\n"
    fact = parse_llms(body, domain="example.com")
    assert fact.present
    assert fact.has_h1
    assert fact.link_count == 2
    assert fact.offsite_link_pct == 0.5
