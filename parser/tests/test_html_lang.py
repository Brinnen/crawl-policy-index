from cpi_parser.html_lang import detect_html_language, primary_language


def test_html_lang_attribute():
    lang, source = detect_html_language(b'<!doctype html><html lang="sv-SE"><head></head>')
    assert lang == "sv"
    assert source == "html_lang"


def test_og_locale_fallback():
    html = b'<html><head><meta property="og:locale" content="sv_SE"></head>'
    lang, source = detect_html_language(html)
    assert lang == "sv"
    assert source == "og_locale"


def test_missing_is_unknown():
    lang, source = detect_html_language(b"<html><body>hello</body></html>")
    assert lang is None
    assert source == "missing"


def test_does_not_map_to_country():
    assert primary_language("sv-SE") == "sv"
    assert primary_language("en") == "en"
