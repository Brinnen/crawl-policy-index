from __future__ import annotations

from cpi_parser.robots import parse, parse_text, path_allowed
from cpi_parser.state import PolicyState, RuleSource, derive_agent, derive_wildcard


def test_blank_lines_do_not_end_group():
    text = "User-agent: GPTBot\n\nDisallow: /private\n"
    parsed = parse_text(text)
    assert len(parsed.groups) == 1
    assert parsed.groups[0].user_agents == ["GPTBot"]
    assert parsed.groups[0].rules[0].value == "/private"


def test_comments_inside_group():
    text = "User-agent: GPTBot\n# keep going\nDisallow: /x\n"
    parsed = parse_text(text)
    assert parsed.groups[0].rules[0].value == "/x"


def test_consecutive_user_agents_same_group():
    text = "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /x\n"
    parsed = parse_text(text)
    assert parsed.groups[0].user_agents == ["GPTBot", "ClaudeBot"]


def test_new_group_after_directive():
    text = (
        "User-agent: GPTBot\nDisallow: /a\n"
        "User-agent: ClaudeBot\nDisallow: /b\n"
    )
    parsed = parse_text(text)
    assert len(parsed.groups) == 2


def test_duplicate_groups_merge_for_matching():
    text = (
        "User-agent: GPTBot\nDisallow: /a\n\n"
        "User-agent: GPTBot\nDisallow: /b\n"
    )
    parsed = parse_text(text)
    group, kind = parsed.group_for_token("GPTBot")
    assert kind == "explicit"
    assert {r.value for r in group.rules} == {"/a", "/b"}


def test_googlebot_image_does_not_match_googlebot():
    text = "User-agent: Googlebot-Image\nDisallow: /\nUser-agent: *\nDisallow:\n"
    parsed = parse_text(text)
    group, kind = parsed.group_for_token("Googlebot")
    assert kind == "wildcard"


def test_empty_disallow_means_allow_everything():
    text = "User-agent: *\nDisallow:\n"
    parsed = parse_text(text)
    assert parsed.groups[0].rules == []
    assert derive_wildcard(parsed)[0] == PolicyState.ALLOWED


def test_empty_allow_ignored():
    text = "User-agent: *\nAllow:\nDisallow: /admin\n"
    parsed = parse_text(text)
    fields = [r.field for r in parsed.groups[0].rules]
    assert "allow" not in fields


def test_allow_beats_disallow_equal_length():
    text = "User-agent: *\nDisallow: /x\nAllow: /x\n"
    parsed = parse_text(text)
    assert path_allowed(parsed.groups[0].rules, "/x") is True
    assert path_allowed(parsed.groups[0].rules, "/x/y") is True


def test_star_and_end_anchor_pdf():
    text = "User-agent: *\nDisallow: /*.pdf$\n"
    parsed = parse_text(text)
    rules = parsed.groups[0].rules
    assert path_allowed(rules, "/doc.pdf") is False
    assert path_allowed(rules, "/doc.pdf.keep") is True
    assert path_allowed(rules, "/") is True


def test_disallow_no_space():
    text = "User-agent: *\nDisallow:/\n"
    parsed = parse_text(text)
    assert derive_wildcard(parsed)[0] == PolicyState.BLOCKED


def test_mixed_case_directives():
    text = "USER-AGENT: *\nDISALLOW: /admin\n"
    parsed = parse_text(text)
    assert parsed.groups[0].user_agents == ["*"]
    assert parsed.groups[0].rules[0].value == "/admin"


def test_utf8_bom_stripped():
    body = b"\xef\xbb\xbfUser-agent: *\nDisallow: /x\n"
    parsed = parse(body)
    assert parsed.groups[0].user_agents == ["*"]


def test_crlf_and_bare_cr():
    parsed = parse(b"User-agent: *\r\nDisallow: /a\r\n")
    assert parsed.groups[0].rules[0].value == "/a"
    parsed = parse(b"User-agent: *\rDisallow: /b\r")
    assert parsed.groups[0].rules[0].value == "/b"


def test_sitemap_is_global():
    text = "User-agent: *\nDisallow: /x\nSitemap: https://example.com/sitemap.xml\n"
    parsed = parse_text(text)
    assert parsed.sitemaps == ["https://example.com/sitemap.xml"]


def test_parse_cap_truncates():
    body = b"User-agent: *\nDisallow: /keep\n" + b"x" * 600_000
    parsed = parse(body, parse_cap_bytes=512_000)
    assert parsed.truncated_for_parse is True
    assert len(parsed.raw_text.encode()) <= 512_000


def test_explicit_block_gptbot():
    text = (
        "User-agent: GPTBot\nDisallow: /\n"
        "User-agent: *\nDisallow: /search\n"
    )
    parsed = parse_text(text)
    policy = derive_agent(parsed, "GPTBot")
    assert policy.state == PolicyState.BLOCKED
    assert policy.rule_source == RuleSource.EXPLICIT
    star = derive_agent(parsed, "ClaudeBot")
    assert star.state == PolicyState.PARTIAL
    assert star.rule_source == RuleSource.WILDCARD


def test_no_wildcard_unnamed_is_none():
    text = "User-agent: GPTBot\nDisallow: /\n"
    parsed = parse_text(text)
    policy = derive_agent(parsed, "ClaudeBot")
    assert policy.state == PolicyState.ALLOWED
    assert policy.rule_source == RuleSource.NONE
    assert derive_wildcard(parsed) == (PolicyState.ALLOWED, False)


def test_crawl_delay():
    text = "User-agent: GPTBot\nCrawl-delay: 10\nDisallow: /x\n"
    parsed = parse_text(text)
    policy = derive_agent(parsed, "GPTBot")
    assert policy.crawl_delay_s == 10.0
