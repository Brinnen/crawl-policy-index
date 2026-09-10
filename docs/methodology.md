# Methodology

This page is the public contract for every published figure. v1 measures **robots.txt only**. Crawl policy that lives in HTTP 402 responses or signed-agent headers is out of scope and must not be inferred from these numbers.

## Panel

Every statistic is of a named, frozen panel version. The panel file and its checksum ship with the tracker. Re-running `panel/build_panel.py` with the same pinned sources and seed must produce a byte-identical CSV.

## Detect gate

Bodies served at `/robots.txt` are classified before parsing. Rows classified `ambiguous`, `not_robots_html`, `not_robots_binary`, or `empty` are excluded from published policy aggregates. The daily distribution of these verdicts is monitored; a 3-point day-over-day shift is treated as parser-corruption until proven otherwise.

## Effective policy

`(domain, agent) → state` is resolved only by `effective_policy(as_of_date)` in the warehouse. That function:

1. considers only `verified AND active` agents from `registry/agents.yml`;
2. uses an explicit `policy_interval` row when the file named the agent;
3. otherwise uses the `*` group (`WILDCARD`) when one exists;
4. otherwise reports `ALLOWED` / `NONE`.

A domain with no trustworthy robots.txt observation is absent from the function's output, not counted as allowing crawlers.

`EXPLICIT` and `WILDCARD` blocks are never conflated in a headline. An explicit block is a deliberate decision; a wildcard block is collateral.

## Tokens that are not crawlers

`Google-Extended`, `Applebot-Extended`, and other `opt_out_token` entries are control signals. They are never summed into crawler-blocking rates.

## Reproducibility

Raw bytes are stored once per SHA-256 and never discarded. A parser bug is fixed by bumping `parse_version` and re-parsing blobs. Prior parse rows are kept.
