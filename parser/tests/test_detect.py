from __future__ import annotations

from cpi_parser.detect import Verdict, classify


def test_empty_bytes():
    assert classify(b"") == Verdict.EMPTY


def test_comments_only():
    assert classify(b"# just a comment\n\n# another\n") == Verdict.EMPTY


def test_wordpress_html_soft404():
    body = b"""<!DOCTYPE html>
<html>
<head><title>Not Found</title></head>
<body><h1>404</h1></body>
</html>
"""
    assert classify(body, "text/html") == Verdict.NOT_ROBOTS_HTML


def test_html_markers_win_even_with_plain_type():
    body = b"<html><head></head><body>nope</body></html>"
    assert classify(body, "text/plain") == Verdict.NOT_ROBOTS_HTML


def test_html_content_type_without_directives():
    body = b"This page cannot be displayed.\nPlease try again later.\n"
    assert classify(body, "text/html") == Verdict.NOT_ROBOTS_HTML


def test_html_content_type_with_directives_no_markers_is_robots():
    body = b"User-agent: *\nDisallow: /secret\n"
    assert classify(body, "text/html") == Verdict.ROBOTS


def test_binary_nuls():
    body = b"\x00" * 200 + b"hello"
    assert classify(body) == Verdict.NOT_ROBOTS_BINARY


def test_utf8_high_bytes_are_not_binary():
    body = "User-agent: *\nDisallow: /\u00e4ll\n".encode()
    assert classify(body) == Verdict.ROBOTS


def test_ambiguous_plain_text():
    body = b"lorem ipsum dolor sit amet, no directives here at all\n"
    assert classify(body, "text/plain") == Verdict.AMBIGUOUS


def test_valid_robots():
    body = b"User-agent: *\nDisallow: /admin\n"
    assert classify(body) == Verdict.ROBOTS


def test_sitemap_only_is_robots():
    body = b"Sitemap: https://example.com/sitemap.xml\n"
    assert classify(body) == Verdict.ROBOTS


def test_utf16_bom_robots():
    body = "User-agent: *\nDisallow: /\n".encode("utf-16")
    assert classify(body) == Verdict.ROBOTS
