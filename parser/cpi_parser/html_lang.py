"""Read a declared page language from a homepage HTML snippet.

This is language, not country. `sv` is Swedish, not Sweden.
Unknown is valid. Do not guess.
"""

from __future__ import annotations

import re

_LANG_ATTR = re.compile(
    r"<html\b[^>]*\b(?:xml:lang|lang)\s*=\s*['\"]?([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)?)['\"]?",
    re.IGNORECASE | re.DOTALL,
)
_META_CONTENT_LANGUAGE = re.compile(
    r"""<meta\b[^>]*http-equiv\s*=\s*['"]content-language['"][^>]*content\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE | re.DOTALL,
)
_META_CONTENT_LANGUAGE_SWAP = re.compile(
    r"""<meta\b[^>]*content\s*=\s*['"]([^'"]+)['"][^>]*http-equiv\s*=\s*['"]content-language['"]""",
    re.IGNORECASE | re.DOTALL,
)
_OG_LOCALE = re.compile(
    r"""<meta\b[^>]*(?:property|name)\s*=\s*['"]og:locale['"][^>]*content\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE | re.DOTALL,
)
_OG_LOCALE_SWAP = re.compile(
    r"""<meta\b[^>]*content\s*=\s*['"]([^'"]+)['"][^>]*(?:property|name)\s*=\s*['"]og:locale['"]""",
    re.IGNORECASE | re.DOTALL,
)

PRIMARY = re.compile(r"^[A-Za-z]{2,3}$")


def primary_language(tag: str | None) -> str | None:
    if not tag:
        return None
    token = tag.strip().replace("_", "-").split(",")[0].strip()
    if not token:
        return None
    primary = token.split("-", 1)[0].lower()
    if PRIMARY.match(primary):
        return primary
    return None


def detect_html_language(body: bytes | str, content_language: str | None = None) -> tuple[str | None, str]:
    """Return (iso639, source). source is html_lang, content_language, og_locale, or missing."""
    if header := primary_language(content_language):
        # Header is a hint; html lang still wins when present.
        html_lang, html_source = _from_html(body)
        if html_lang:
            return html_lang, html_source
        return header, "content_language"
    return _from_html(body)


def _from_html(body: bytes | str) -> tuple[str | None, str]:
    if isinstance(body, bytes):
        text = body[:80_000].decode("utf-8", errors="replace")
    else:
        text = body[:80_000]
    m = _LANG_ATTR.search(text)
    if m and (lang := primary_language(m.group(1))):
        return lang, "html_lang"
    for rx in (_META_CONTENT_LANGUAGE, _META_CONTENT_LANGUAGE_SWAP):
        m = rx.search(text)
        if m and (lang := primary_language(m.group(1))):
            return lang, "content_language"
    for rx in (_OG_LOCALE, _OG_LOCALE_SWAP):
        m = rx.search(text)
        if m and (lang := primary_language(m.group(1))):
            return lang, "og_locale"
    return None, "missing"
