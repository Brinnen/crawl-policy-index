"""Write the hand-authored golden corpus. Run from repo root."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES: list[tuple[str, bytes, dict]] = []


def add(name: str, body: bytes | str, expected: dict) -> None:
    if isinstance(body, str):
        body = body.encode("utf-8")
    CASES.append((name, body, expected))


add(
    "html_soft404_wordpress",
    """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Page not found</title></head>
<body class="error404"><h1>Oops! That page can&rsquo;t be found.</h1></body>
</html>
""",
    {"detect": "not_robots_html", "content_type": "text/html"},
)

add(
    "html_soft404_cloudflare",
    """<!DOCTYPE html>
<html>
<head><title>Attention Required! | Cloudflare</title></head>
<body>
<div class="cf-wrapper">Error 1020</div>
</body>
</html>
""",
    {"detect": "not_robots_html"},
)

add(
    "html_soft404_iis",
    """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html><head><title>The resource cannot be found.</title></head>
<body><span><h1>Server Error in '/' Application.<hr width="100%"></h1></span></body></html>
""",
    {"detect": "not_robots_html", "content_type": "text/html"},
)

add(
    "html_soft404_generic",
    "<html><head></head><body>404 Not Found</body></html>\n",
    {"detect": "not_robots_html"},
)

add(
    "blank_lines_inside_group",
    "User-agent: GPTBot\n\n\nDisallow: /private\n",
    {
        "detect": "robots",
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": False},
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "EXPLICIT"}
        },
    },
)

add(
    "comments_inside_group",
    "User-agent: GPTBot\n# internal note\nDisallow: /hidden\n",
    {
        "detect": "robots",
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "EXPLICIT"}
        },
    },
)

add(
    "duplicate_ua_two_groups",
    "User-agent: GPTBot\nDisallow: /a\n\nUser-agent: GPTBot\nDisallow: /b\n",
    {
        "detect": "robots",
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "EXPLICIT"}
        },
    },
)

add(
    "disallow_empty_value",
    "User-agent: *\nDisallow:\n",
    {
        "detect": "robots",
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "ALLOWED", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "allow_empty_value",
    "User-agent: *\nAllow:\nDisallow: /admin\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "equal_length_allow_wins",
    "User-agent: *\nDisallow: /x\nAllow: /x\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "wildcard_star_and_end_anchor",
    "User-agent: *\nDisallow: /*.pdf$\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "disallow_no_space",
    "User-agent: *\nDisallow:/\n",
    {
        "detect": "robots",
        "wildcard": {"state": "BLOCKED", "has_wildcard_group": True},
        "agents": {
            "google-googlebot": {"state": "BLOCKED", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "mixed_case_directives",
    "USER-AGENT: *\nDISALLOW: /search\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "utf8_bom",
    b"\xef\xbb\xbfUser-agent: *\nDisallow: /tmp\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "utf16_bom",
    "User-agent: *\nDisallow: /tmp\n".encode("utf-16"),
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "latin1_bytes",
    "User-agent: *\nDisallow: /\xe4\n".encode("latin-1"),
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "embedded_nuls",
    b"\x00\x00\x00" + b"\x01" * 400,
    {"detect": "not_robots_binary"},
)

add(
    "crlf_endings",
    b"User-agent: *\r\nDisallow: /admin\r\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "bare_cr_endings",
    b"User-agent: *\rDisallow: /admin\r",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "mixed_line_endings",
    b"User-agent: *\r\nDisallow: /a\nDisallow: /b\r",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "sitemap_only",
    "Sitemap: https://example.com/sitemap.xml\nSitemap: https://example.com/news.xml\n",
    {
        "detect": "robots",
        "sitemaps": [
            "https://example.com/sitemap.xml",
            "https://example.com/news.xml",
        ],
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": False},
        "agents": {
            "openai-gptbot": {"state": "ALLOWED", "rule_source": "NONE"}
        },
    },
)

add(
    "non_ascii_ua",
    "User-agent: B\u00f6t\nDisallow: /\nUser-agent: *\nDisallow: /tmp\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "empty_file",
    b"",
    {"detect": "empty"},
)

add(
    "comments_only",
    "# robots.txt\n# nothing else\n",
    {"detect": "empty"},
)

add(
    "ambiguous_plain_text",
    "Welcome to our website. There is nothing to see here.\nCome back later.\n",
    {"detect": "ambiguous", "content_type": "text/plain"},
)

add(
    "html_content_type_no_directives",
    "Object not found!\nThe requested URL was not found on this server.\n",
    {"detect": "not_robots_html", "content_type": "text/html"},
)

add(
    "explicit_gptbot_block_star_partial",
    "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /search\nAllow: /\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "openai-searchbot": {"state": "PARTIAL", "rule_source": "WILDCARD"},
            "google-googlebot": {"state": "PARTIAL", "rule_source": "WILDCARD"},
        },
    },
)

add(
    "googlebot_image_not_googlebot",
    "User-agent: Googlebot-Image\nDisallow: /\n\nUser-agent: *\nDisallow:\n",
    {
        "detect": "robots",
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": True},
        "agents": {
            "google-googlebot": {"state": "ALLOWED", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "named_only_no_wildcard",
    "User-agent: GPTBot\nDisallow: /\n",
    {
        "detect": "robots",
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": False},
        "agents": {
            "openai-gptbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "anthropic-claudebot": {"state": "ALLOWED", "rule_source": "NONE"},
        },
    },
)

add(
    "bytespider_block_star_allow",
    "User-agent: Bytespider\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
    {
        "detect": "robots",
        "wildcard": {"state": "ALLOWED", "has_wildcard_group": True},
        "agents": {
            "bytedance-bytespider": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "openai-gptbot": {"state": "ALLOWED", "rule_source": "WILDCARD"},
        },
    },
)

add(
    "training_vs_search_split",
    """User-agent: GPTBot
Disallow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: *
Disallow: /drafts
""",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "openai-searchbot": {"state": "ALLOWED", "rule_source": "EXPLICIT"},
            "openai-chatgpt-user": {"state": "ALLOWED", "rule_source": "EXPLICIT"},
        },
    },
)

add(
    "allow_overrides_root_disallow",
    "User-agent: *\nDisallow: /\nAllow: /\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)

add(
    "crawl_delay_explicit",
    "User-agent: CCBot\nCrawl-delay: 5\nDisallow: /api\n",
    {
        "detect": "robots",
        "agents": {
            "commoncrawl-ccbot": {"state": "PARTIAL", "rule_source": "EXPLICIT"}
        },
    },
)

add(
    "publisher_nytimes_shape",
    """User-agent: *
Disallow: /ads/
Disallow: /search
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /
""",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "google-extended": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "commoncrawl-ccbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "google-googlebot": {"state": "PARTIAL", "rule_source": "WILDCARD"},
        },
    },
)

add(
    "publisher_github_shape",
    """User-agent: *
Disallow: /*/pulse
Disallow: /login
Allow: /

Sitemap: https://github.com/sitemap.xml
""",
    {
        "detect": "robots",
        "sitemaps": ["https://github.com/sitemap.xml"],
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "PARTIAL", "rule_source": "WILDCARD"}
        },
    },
)

add(
    "publisher_bbc_shape",
    """User-agent: *
Disallow: /search
Disallow: /bitesize/search

User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /
""",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
        "agents": {
            "openai-gptbot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "anthropic-claudebot": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "microsoft-bingbot": {"state": "PARTIAL", "rule_source": "WILDCARD"},
        },
    },
)

add(
    "google_extended_not_a_crawler_named",
    "User-agent: Google-Extended\nDisallow: /\nUser-agent: Googlebot\nAllow: /\n",
    {
        "detect": "robots",
        "agents": {
            "google-extended": {"state": "BLOCKED", "rule_source": "EXPLICIT"},
            "google-googlebot": {"state": "ALLOWED", "rule_source": "EXPLICIT"},
        },
    },
)

add(
    "user_agent_then_blank_then_disallow",
    "User-agent: *\n\n# comment\n\nDisallow: /cgi-bin\n",
    {
        "detect": "robots",
        "wildcard": {"state": "PARTIAL", "has_wildcard_group": True},
    },
)


def main() -> None:
    for name, body, expected in CASES:
        (ROOT / f"{name}.txt").write_bytes(body)
        (ROOT / f"{name}.expected.json").write_text(
            json.dumps(expected, indent=2) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(CASES)} cases")


if __name__ == "__main__":
    main()
