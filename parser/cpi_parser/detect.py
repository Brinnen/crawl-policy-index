"""Classify whether a fetched body is actually a robots.txt.

This is the highest-risk function in the codebase. Hosts commonly answer
``/robots.txt`` with HTTP 200 and an HTML error page. A naive parser then
records the site as allowing every AI crawler.

``ambiguous`` rows are excluded from every published aggregate.
"""

from __future__ import annotations

from enum import StrEnum

KNOWN_DIRECTIVES = frozenset(
    {
        "user-agent",
        "allow",
        "disallow",
        "crawl-delay",
        "request-rate",
        "visit-time",
        "sitemap",
        "host",
    }
)

HTML_MARKERS = (b"<!doctype", b"<html", b"<head", b"<body")

_WHITESPACE = frozenset({9, 10, 11, 12, 13, 32})


class Verdict(StrEnum):
    ROBOTS = "robots"
    NOT_ROBOTS_HTML = "not_robots_html"
    NOT_ROBOTS_BINARY = "not_robots_binary"
    EMPTY = "empty"
    AMBIGUOUS = "ambiguous"


def classify(body: bytes, content_type: str | None = None) -> Verdict:
    if body.startswith(b"\xff\xfe") or body.startswith(b"\xfe\xff"):
        text = body.decode("utf-16", errors="replace")
        raw_for_html = text.encode("utf-8", errors="replace")
        return _classify_text(text, raw_for_html, content_type)

    if body.startswith(b"\xef\xbb\xbf"):
        rest = body[3:]
    else:
        rest = body

    if _is_binary(rest[:8192]):
        return Verdict.NOT_ROBOTS_BINARY

    text = rest.decode("utf-8", errors="replace")
    return _classify_text(text, rest, content_type)


def _classify_text(text: str, raw: bytes, content_type: str | None) -> Verdict:
    if _is_empty(text):
        return Verdict.EMPTY

    first_2k = raw[:2048].lower()
    has_html_marker = any(marker in first_2k for marker in HTML_MARKERS)
    has_directive = _has_directive_line(text)
    ct = (content_type or "").split(";")[0].strip().lower()
    html_ct = ct == "text/html"

    if has_html_marker or (html_ct and not has_directive):
        return Verdict.NOT_ROBOTS_HTML

    if not has_directive:
        return Verdict.AMBIGUOUS

    return Verdict.ROBOTS


def _is_binary(sample: bytes) -> bool:
    if not sample:
        return False
    bad = sum(1 for b in sample if _is_nonprintable_nonws(b))
    return (bad / len(sample)) > 0.02


def _is_nonprintable_nonws(b: int) -> bool:
    if b in _WHITESPACE:
        return False
    if 32 <= b <= 126:
        return False
    if b >= 128:
        return False
    return True


def _is_empty(text: str) -> bool:
    for line in _split_lines(text):
        stripped = _strip_comment(line).strip()
        if stripped:
            return False
    return True


def _has_directive_line(text: str) -> bool:
    for line in _split_lines(text):
        stripped = _strip_comment(line).strip()
        if not stripped or ":" not in stripped:
            continue
        name = stripped.split(":", 1)[0].strip().lower()
        if name in KNOWN_DIRECTIVES:
            return True
    return False


def _strip_comment(line: str) -> str:
    idx = line.find("#")
    if idx == -1:
        return line
    return line[:idx]


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
