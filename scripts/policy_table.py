"""Turn fetched robots.txt files into a readable policy table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from cpi_parser.detect import classify
from cpi_parser.registry import load_agents
from cpi_parser.robots import parse
from cpi_parser.state import derive_agent, derive_wildcard

ROOT = Path(__file__).resolve().parents[1]

HEADLINE = (
    "openai-gptbot",
    "openai-searchbot",
    "anthropic-claudebot",
    "google-googlebot",
    "google-extended",
    "commoncrawl-ccbot",
    "perplexity-bot",
    "bytedance-bytespider",
    "meta-externalagent",
)

HOW = {
    "EXPLICIT": "named",
    "WILDCARD": "inherited",
    "NONE": "unnamed",
}

STATE = {
    "ALLOWED": "allow",
    "PARTIAL": "partial",
    "BLOCKED": "BLOCK",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(ROOT / "data" / "smoke"))
    p.add_argument("--registry", default=str(ROOT / "registry" / "agents.yml"))
    p.add_argument("--out", default=str(ROOT / "data" / "policy-table.csv"))
    p.add_argument(
        "--print-rows",
        type=int,
        default=-1,
        help="Domain rows to print. 0 = summary only. -1 = print if ≤40 domains.",
    )
    args = p.parse_args(argv)

    agents = load_agents(args.registry)
    by_slug = {a.slug: a for a in agents}
    headline = [by_slug[s] for s in HEADLINE if s in by_slug]
    inp = Path(args.input)
    rows: list[dict[str, str]] = []

    domains = sorted(d for d in inp.iterdir() if d.is_dir())
    remaining = args.print_rows
    if remaining < 0:
        remaining = 40 if len(domains) <= 40 else 0
    named_gptbot_blocks: list[str] = []
    openai_split = 0

    print("")
    print("Policy table (headline bots)")
    print("  allow   = may crawl the homepage")
    print("  partial = homepage ok, some folders off limits")
    print("  BLOCK   = homepage forbidden")
    print("  *       = the site named this bot on purpose")
    print("  no *    = inherited from the * (everyone) rules")
    print("")
    names = [_short(a.display_name) for a in headline]
    header = f"{'domain':18} " + " ".join(f"{n:12}" for n in names)
    if remaining:
        print(header)
        print("-" * len(header))
    else:
        print(f"{len(domains)} domains — not printing every row. Summary below; full CSV is saved.")
        print("")

    for domain_dir in domains:
        robots = domain_dir / "robots.txt"
        domain = domain_dir.name
        if not robots.exists() or robots.stat().st_size == 0:
            if remaining:
                print(f"{domain:18} (no robots.txt saved)")
                remaining -= 1
            rows.append(_meta_row(domain, "missing", "no file saved"))
            continue
        body = robots.read_bytes()
        verdict = str(classify(body))
        if verdict != "robots":
            if remaining:
                print(f"{domain:18} (not a real robots.txt: {verdict})")
                remaining -= 1
            rows.append(_meta_row(domain, verdict, "excluded from policy"))
            continue
        parsed = parse(body)
        wc_state, has_wc = derive_wildcard(parsed)
        cells = []
        headline_pols = {}
        for a in headline:
            pol = derive_agent(parsed, a.ua_token)
            headline_pols[a.slug] = pol
            cells.append(_cell(str(pol.state), str(pol.rule_source)))
        gpt = headline_pols.get("openai-gptbot")
        search = headline_pols.get("openai-searchbot")
        if (
            gpt is not None
            and search is not None
            and str(gpt.state) == "BLOCKED"
            and str(gpt.rule_source) == "EXPLICIT"
            and str(search.state) != "BLOCKED"
        ):
            openai_split += 1
        if gpt is not None and str(gpt.state) == "BLOCKED" and str(gpt.rule_source) == "EXPLICIT":
            named_gptbot_blocks.append(domain)
        if remaining:
            print(f"{domain:18} " + " ".join(f"{c:12}" for c in cells))
            remaining -= 1
        for a in agents:
            pol = derive_agent(parsed, a.ua_token)
            rows.append(
                {
                    "domain": domain,
                    "agent": a.display_name,
                    "slug": a.slug,
                    "operator": a.operator,
                    "purpose": a.purpose,
                    "state": str(pol.state),
                    "how": HOW[str(pol.rule_source)],
                    "wildcard_state": str(wc_state),
                    "has_star_group": "yes" if has_wc else "no",
                    "detect": verdict,
                }
            )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "domain",
        "agent",
        "slug",
        "operator",
        "purpose",
        "state",
        "how",
        "wildcard_state",
        "has_star_group",
        "detect",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    gpt_rows = [r for r in rows if r.get("slug") == "openai-gptbot"]
    named_block = sum(1 for r in gpt_rows if r["state"] == "BLOCKED" and r["how"] == "named")
    named_allow = sum(1 for r in gpt_rows if r["state"] == "ALLOWED" and r["how"] == "named")
    inherited = sum(1 for r in gpt_rows if r["how"] != "named")
    google_block = sum(
        1
        for r in rows
        if r.get("slug") == "google-googlebot" and r["state"] == "BLOCKED"
    )
    print("")
    print(f"GPTBot among sites with a real robots.txt: {len(gpt_rows)}")
    print(f"  named block={named_block}  named allow={named_allow}  not named (inherited)={inherited}")
    print(f"  named GPTBot block but OpenAI search allowed: {openai_split}")
    print(f"Googlebot BLOCK (sanity; should be near 0): {google_block}")
    if named_gptbot_blocks:
        show = named_gptbot_blocks[:25]
        extra = len(named_gptbot_blocks) - len(show)
        print("Named GPTBot blocks:")
        print("  " + ", ".join(show) + (f" … +{extra} more" if extra > 0 else ""))
    print("")
    print("Full table (every bot) saved to:")
    print(f"  {out}")
    return 0


def _cell(state: str, source: str) -> str:
    label = STATE[state]
    if source == "EXPLICIT":
        return f"{label}*"
    return label


def _short(name: str) -> str:
    return name.replace(" (legacy)", "")[:12]


def _meta_row(domain: str, detect: str, how: str) -> dict[str, str]:
    return {
        "domain": domain,
        "agent": "",
        "slug": "",
        "operator": "",
        "purpose": "",
        "state": "",
        "how": how,
        "wildcard_state": "",
        "has_star_group": "",
        "detect": detect,
    }


if __name__ == "__main__":
    raise SystemExit(main())
