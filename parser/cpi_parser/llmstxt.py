"""Structural parse of llms.txt. No semantics; adoption only, never a headline."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")


@dataclass(frozen=True)
class LlmsTxtFact:
    present: bool
    byte_len: int
    parses_markdown: bool
    has_h1: bool
    section_count: int
    link_count: int
    offsite_link_pct: float | None


def parse(body: bytes, domain: str | None = None) -> LlmsTxtFact:
    if not body:
        return LlmsTxtFact(
            present=False,
            byte_len=0,
            parses_markdown=False,
            has_h1=False,
            section_count=0,
            link_count=0,
            offsite_link_pct=None,
        )
    text = body.decode("utf-8", errors="replace")
    tokens = _md.parse(text)
    has_h1 = any(t.type == "heading_open" and t.tag == "h1" for t in tokens)
    section_count = sum(1 for t in tokens if t.type == "heading_open")
    links = _collect_links(text)
    offsite = None
    if links and domain:
        off = sum(1 for href in links if _is_offsite(href, domain))
        offsite = off / len(links)
    parses = bool(tokens) and (has_h1 or section_count > 0 or bool(links) or text.strip().startswith("#"))
    return LlmsTxtFact(
        present=True,
        byte_len=len(body),
        parses_markdown=parses or bool(text.strip()),
        has_h1=has_h1,
        section_count=section_count,
        link_count=len(links),
        offsite_link_pct=offsite,
    )


def _collect_links(text: str) -> list[str]:
    hrefs: list[str] = []
    for line in text.splitlines():
        start = 0
        while True:
            i = line.find("](", start)
            if i == -1:
                break
            j = line.find(")", i + 2)
            if j == -1:
                break
            hrefs.append(line[i + 2 : j].strip().split()[0] if line[i + 2 : j].strip() else "")
            start = j + 1
    return [h for h in hrefs if h]


def _is_offsite(href: str, domain: str) -> bool:
    parsed = urlparse(href)
    if not parsed.netloc:
        return False
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    domain = domain.lower()
    return host != domain and not host.endswith("." + domain)
