from __future__ import annotations

from cpi_parser.detect import classify
from cpi_parser.robots import parse


def test_two_mib_file_sets_truncated_for_parse():
    header = b"User-agent: *\nDisallow: /keep-me\n"
    body = header + (b"# padding\n" * 300_000)
    assert len(body) > 2 * 1024 * 1024
    assert str(classify(body)) == "robots"
    parsed = parse(body)
    assert parsed.truncated_for_parse is True
    assert parsed.groups[0].rules[0].value == "/keep-me"
