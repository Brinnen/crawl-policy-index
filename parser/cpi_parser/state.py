"""Derive policy state and rule_source from a parsed robots.txt."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from cpi_parser.robots import Group, ParsedRobots, path_allowed


class PolicyState(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class RuleSource(StrEnum):
    EXPLICIT = "EXPLICIT"
    WILDCARD = "WILDCARD"
    NONE = "NONE"


@dataclass(frozen=True)
class AgentPolicy:
    state: PolicyState
    rule_source: RuleSource
    crawl_delay_s: float | None
    matched_ua_token: str


def derive_agent(parsed: ParsedRobots, ua_token: str) -> AgentPolicy:
    group, kind = parsed.group_for_token(ua_token)
    if kind == "none" or group is None:
        return AgentPolicy(
            state=PolicyState.ALLOWED,
            rule_source=RuleSource.NONE,
            crawl_delay_s=None,
            matched_ua_token=ua_token,
        )
    source = RuleSource.EXPLICIT if kind == "explicit" else RuleSource.WILDCARD
    return AgentPolicy(
        state=_state_from_group(group),
        rule_source=source,
        crawl_delay_s=_crawl_delay(group),
        matched_ua_token=ua_token,
    )


def derive_wildcard(parsed: ParsedRobots) -> tuple[PolicyState, bool]:
    wild: list[Group] = [
        g for g in parsed.groups if any(a == "*" for a in g.user_agents)
    ]
    if not wild:
        return PolicyState.ALLOWED, False
    merged_rules = [r for g in wild for r in g.rules]
    fake = Group(user_agents=["*"], rules=merged_rules)
    return _state_from_group(fake), True


def derive_all(
    parsed: ParsedRobots, ua_tokens: Iterable[tuple[str, str]]
) -> dict[str, AgentPolicy]:
    """ua_tokens is iterable of (slug, ua_token)."""
    return {slug: derive_agent(parsed, token) for slug, token in ua_tokens}


def _state_from_group(group: Group) -> PolicyState:
    non_empty_disallow = [r for r in group.rules if r.field == "disallow"]
    if not non_empty_disallow:
        return PolicyState.ALLOWED
    root_allowed = path_allowed(group.rules, "/")
    if not root_allowed:
        return PolicyState.BLOCKED
    return PolicyState.PARTIAL


def _crawl_delay(group: Group) -> float | None:
    values = group.extras.get("crawl-delay") or []
    for raw in values:
        try:
            return float(raw)
        except ValueError:
            continue
    return None
