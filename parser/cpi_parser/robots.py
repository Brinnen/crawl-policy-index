"""RFC 9309 robots.txt parser.

Ambiguities are resolved the way Google's reference implementation does,
because that is what site owners actually test against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from cpi_parser.detect import KNOWN_DIRECTIVES

PARSE_CAP_BYTES = 512_000

_PATH_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


@dataclass(frozen=True)
class Rule:
    field: str  # allow | disallow
    value: str
    length: int


@dataclass
class Group:
    user_agents: list[str]
    rules: list[Rule] = field(default_factory=list)
    extras: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ParsedRobots:
    groups: list[Group]
    sitemaps: list[str]
    extras: dict[str, list[str]]
    truncated_for_parse: bool
    raw_text: str

    def group_for_token(self, ua_token: str) -> tuple[Group | None, str]:
        """Return (merged group, match kind).

        match kind is ``explicit``, ``wildcard``, or ``none``.
        Exact token match, case-insensitive, not substring. Longest
        matching token wins if several named groups could apply — with
        exact matching that is a no-op, kept for the spec's wording.
        Duplicate groups for the same token are merged.
        """
        needle = ua_token.casefold()
        matching: list[Group] = []
        for group in self.groups:
            for agent in group.user_agents:
                if agent.casefold() == needle:
                    matching.append(group)
                    break
        if matching:
            return _merge_groups(matching), "explicit"

        wild = [g for g in self.groups if any(a == "*" for a in g.user_agents)]
        if wild:
            return _merge_groups(wild), "wildcard"
        return None, "none"


def parse(body: bytes, parse_cap_bytes: int = PARSE_CAP_BYTES) -> ParsedRobots:
    truncated = len(body) > parse_cap_bytes
    if truncated:
        body = body[:parse_cap_bytes]
    text = _decode_body(body)
    return parse_text(text, truncated_for_parse=truncated)


def parse_text(text: str, truncated_for_parse: bool = False) -> ParsedRobots:
    groups: list[Group] = []
    sitemaps: list[str] = []
    extras: dict[str, list[str]] = {}

    current: Group | None = None
    saw_non_ua = False

    for raw_line in _split_lines(text):
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip().lower()
        value = value.strip()

        if name == "user-agent":
            if current is None or saw_non_ua:
                current = Group(user_agents=[])
                groups.append(current)
                saw_non_ua = False
            if value:
                current.user_agents.append(value)
            continue

        if current is None:
            # Directives before any User-agent: treat Sitemap as global;
            # anything else goes to extras.
            if name == "sitemap":
                if value:
                    sitemaps.append(value)
            else:
                extras.setdefault(name, []).append(value)
            continue

        saw_non_ua = True

        if name == "sitemap":
            if value:
                sitemaps.append(value)
            continue

        if name == "disallow":
            if value == "":
                continue
            current.rules.append(Rule(field="disallow", value=value, length=len(value)))
            continue

        if name == "allow":
            if value == "":
                continue
            current.rules.append(Rule(field="allow", value=value, length=len(value)))
            continue

        current.extras.setdefault(name, []).append(value)
        extras.setdefault(name, []).append(value)

    return ParsedRobots(
        groups=groups,
        sitemaps=sitemaps,
        extras=extras,
        truncated_for_parse=truncated_for_parse,
        raw_text=text,
    )


def path_allowed(rules: list[Rule], path: str) -> bool:
    """Longest matching rule wins; on equal length, Allow beats Disallow."""
    decoded_path = percent_decode_except_slash(path)
    best_allow: int | None = None
    best_disallow: int | None = None
    for rule in rules:
        if not _path_matches(rule.value, decoded_path):
            continue
        n = rule.length
        if rule.field == "allow":
            if best_allow is None or n > best_allow:
                best_allow = n
        elif rule.field == "disallow":
            if best_disallow is None or n > best_disallow:
                best_disallow = n

    if best_disallow is None:
        return True
    if best_allow is None:
        return False
    if best_allow > best_disallow:
        return True
    if best_allow < best_disallow:
        return False
    return True


def percent_decode_except_slash(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            hexv = s[i + 1 : i + 3]
            if hexv.upper() == "2F":
                out.append("%2F")
                i += 3
                continue
            try:
                out.append(chr(int(hexv, 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _path_matches(pattern: str, path: str) -> bool:
    decoded_pattern = percent_decode_except_slash(pattern)
    regex = _compile_path_pattern(decoded_pattern)
    return regex.search(path) is not None


def _compile_path_pattern(pattern: str) -> re.Pattern[str]:
    cached = _PATH_REGEX_CACHE.get(pattern)
    if cached is not None:
        return cached
    parts: list[str] = ["^"]
    for i, ch in enumerate(pattern):
        if ch == "*":
            parts.append(".*")
        elif ch == "$" and i == len(pattern) - 1:
            parts.append("$")
        else:
            parts.append(re.escape(ch))
    compiled = re.compile("".join(parts))
    _PATH_REGEX_CACHE[pattern] = compiled
    return compiled


def _merge_groups(groups: list[Group]) -> Group:
    agents: list[str] = []
    seen_agents: set[str] = set()
    rules: list[Rule] = []
    extras: dict[str, list[str]] = {}
    for g in groups:
        for a in g.user_agents:
            key = a.casefold()
            if key not in seen_agents:
                seen_agents.add(key)
                agents.append(a)
        rules.extend(g.rules)
        for k, vals in g.extras.items():
            extras.setdefault(k, []).extend(vals)
    return Group(user_agents=agents, rules=rules, extras=extras)


def _decode_body(body: bytes) -> str:
    if body.startswith(b"\xff\xfe") or body.startswith(b"\xfe\xff"):
        return body.decode("utf-16", errors="replace")
    if body.startswith(b"\xef\xbb\xbf"):
        return body[3:].decode("utf-8", errors="replace")
    return body.decode("utf-8", errors="replace")


def _strip_comment(line: str) -> str:
    idx = line.find("#")
    if idx == -1:
        return line
    return line[:idx]


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


@lru_cache(maxsize=1)
def _known() -> frozenset[str]:
    return KNOWN_DIRECTIVES
