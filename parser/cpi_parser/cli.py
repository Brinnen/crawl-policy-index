"""Parser CLI.

``parse``  — one local file to JSON (dev).
``reparse`` — blobs whose content hash changed; idempotent per (blob, parse_version).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cpi_parser import __version__
from cpi_parser.detect import classify
from cpi_parser.llmstxt import parse as parse_llms
from cpi_parser.registry import load_agents
from cpi_parser.robots import parse as parse_robots
from cpi_parser.sitemap import parse as parse_sitemap
from cpi_parser.state import derive_agent, derive_wildcard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cpi_parser")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="Parse a local file to JSON")
    p_parse.add_argument("--file", required=True)
    p_parse.add_argument("--resource", default="robots_txt", choices=["robots_txt", "llms_txt", "sitemap_xml"])
    p_parse.add_argument("--registry", default="registry/agents.yml")
    p_parse.add_argument("--content-type", default=None)
    p_parse.add_argument("--domain", default=None)

    p_reparse = sub.add_parser("reparse", help="Re-parse stored blobs (WP4 derive)")
    p_reparse.add_argument("--resource", default="robots_txt")
    p_reparse.add_argument("--since", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "parse":
        return _cmd_parse(args)
    print(
        "reparse requires the warehouse derive pipeline (WP4). "
        "Use `parse` against a local file until loaders are wired.",
        file=sys.stderr,
    )
    return 2


def _cmd_parse(args: argparse.Namespace) -> int:
    body = Path(args.file).read_bytes()
    if args.resource == "robots_txt":
        verdict = classify(body, args.content_type)
        payload: dict = {
            "parse_version": __version__,
            "detect": str(verdict),
        }
        if verdict == "robots":
            parsed = parse_robots(body)
            agents = load_agents(args.registry) if Path(args.registry).exists() else []
            wc_state, has_wc = derive_wildcard(parsed)
            payload.update(
                {
                    "truncated_for_parse": parsed.truncated_for_parse,
                    "sitemaps": parsed.sitemaps,
                    "groups": [
                        {
                            "user_agents": g.user_agents,
                            "rules": [
                                {"field": r.field, "value": r.value} for r in g.rules
                            ],
                        }
                        for g in parsed.groups
                    ],
                    "wildcard": {"state": str(wc_state), "has_wildcard_group": has_wc},
                    "agents": {
                        a.slug: _agent_dict(derive_agent(parsed, a.ua_token))
                        for a in agents
                    },
                }
            )
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.resource == "llms_txt":
        fact = parse_llms(body, domain=args.domain)
        json.dump(fact.__dict__, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0
    fact = parse_sitemap(body)
    json.dump(
        {
            "present": fact.present,
            "root_element": fact.root_element,
            "child_count": fact.child_count,
            "lastmod_min": fact.lastmod_min.isoformat() if fact.lastmod_min else None,
            "lastmod_max": fact.lastmod_max.isoformat() if fact.lastmod_max else None,
            "lastmod_coverage": fact.lastmod_coverage,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _agent_dict(policy) -> dict:
    return {
        "state": str(policy.state),
        "rule_source": str(policy.rule_source),
        "crawl_delay_s": policy.crawl_delay_s,
    }


if __name__ == "__main__":
    raise SystemExit(main())
