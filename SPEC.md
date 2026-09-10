# Crawl Policy Index — Engineering Specification

**Version** 1.0 · **Date** 2026-09-08 · **Status** ready to build
**Stack** Go (fetcher) · Python 3.12 (parser, backfill, pipeline) · PostgreSQL 16 · Cloudflare R2 · Astro (static site)

---

## 0. What we are building, in one paragraph

A daily, longitudinal record of **site-declared AI crawl policy** — which AI agents each domain in a defined panel allows, blocks, or partially restricts — reconstructed backwards to 2022 where the Internet Archive permits, and published as a free public tracker plus an annual report.

The system is a straight line: fetch three text files per domain per day → store raw bytes once per unique content hash → parse into policy intervals → roll up → render a static site.

### The three invariants

Everything in this spec exists to protect one of these. If a design decision conflicts with them, the invariant wins.

1. **No missing days.** A day not collected is unrecoverable. The fetcher must degrade rather than stop. Partial data beats no data.
2. **Raw bytes are immutable and permanent.** Every parse is reproducible from stored blobs. Parser bugs are always fixable retroactively; that is only true if we never discard input.
3. **No published number without a traceable derivation.** Every figure on the site resolves to one SQL view over one parse version over one panel version.

### Non-goals for v1 — do not build these

- Following child sitemaps or expanding sitemap URLs. We record top-level metadata only.
- Any log-based or traffic-volume data.
- User accounts, auth, billing, dashboards.
- Real-time or on-demand fetching. Everything is a batch run.
- Anything that reads or stores personal data. There is none in scope; keep it that way.

---

## 1. Repository layout

Monorepo, one CI pipeline, independent deployables.

```
crawl-policy-index/
├── README.md
├── SPEC.md                     ← this document
├── docker-compose.dev.yml      Postgres + MinIO for local work
├── Makefile                    make dev-up, make test, make fetch-local
│
├── registry/
│   ├── agents.yml              WP2  agent registry (source of truth, code-reviewed)
│   └── verticals.yml           WP0  vertical taxonomy + domain assignments
│
├── panel/                      WP0  Python — panel construction
│   ├── build_panel.py          emits panel-YYYYQN.csv, deterministic
│   └── sources/                tranco.py, ct_logs.py, zone_files.py, curated_news.py
│
├── fetcher/                    WP1  Go 1.23
│   ├── cmd/cpifetch/main.go
│   └── internal/
│       ├── panel/              load + shard the panel
│       ├── fetch/              HTTP client, politeness, redirect policy
│       ├── store/              R2 blob + NDJSON observation writer
│       └── report/             gap report, run manifest
│
├── parser/                     WP2  Python — the correctness-critical package
│   ├── cpi_parser/
│   │   ├── robots.py           RFC 9309 parser
│   │   ├── detect.py           "is this actually robots.txt?" gate
│   │   ├── state.py            state + rule_source derivation
│   │   ├── llmstxt.py          llms.txt structural parse
│   │   └── sitemap.py          top-level sitemap metadata only
│   └── tests/
│       ├── corpus/             500 golden cases: <case>.txt + <case>.expected.json
│       └── differential/       10k-sample agreement harness vs reference parser
│
├── backfill/                   WP3  Python — Internet Archive reconstruction
│   └── wayback.py
│
├── warehouse/                  WP4  SQL + Python
│   ├── migrations/             0001_init.sql … (sqlmigrate or alembic-style, forward-only)
│   ├── load/                   NDJSON → Postgres COPY loaders
│   ├── derive/                 blob → policy_interval materialisation
│   └── rollups/                *.sql, one file per published view
│
├── site/                       WP5  Astro — static tracker
│   ├── src/pages/
│   ├── src/charts/             build-time SVG generation, zero client JS
│   └── scripts/export.py       Postgres → JSON/CSV build inputs
│
├── report/                     WP6  launch report + print PDF
│
└── docs/
    ├── methodology.md          public — the page researchers will judge us on
    ├── runbook.md              on-call: what alerts mean, how to recover
    └── decisions/              ADRs, one file per irreversible choice
```

---

## 2. WP0 — Panel construction

*Python · 3–4 days · must complete before WP1 can run*

The panel is a **frozen, versioned, publicly downloadable list**. It is the single most load-bearing artefact in the project: every statistic we publish is "of panel X". Axel owns its definition; the dev owns making it reproducible.

### Composition — `panel-2026Q4`

| Stratum | Source | Target size | Notes |
|---|---|---|---|
| `head` | Tranco top 1M, pinned list ID | 1,000,000 | Record the exact Tranco list ID and date in the manifest. Never "latest". |
| `news` | Curated, ~120 countries | ~8,000 | Hand-maintained YAML. Highest-signal stratum. |
| `nordic` | `.se` `.no` `.dk` `.fi` zone samples | ~25,000 | Random sample, seeded. |
| `tail` | Random sample from Certificate Transparency logs | ~50,000 | Guards the "top 1M isn't the web" objection. |

De-duplicate across strata; a domain may carry multiple stratum tags. Store the registrable domain (eTLD+1) via the Public Suffix List — **pin the PSL version**, it changes.

### Output

`panel-2026Q4.csv`, checksummed, published alongside the tracker:

```
domain,strata,tranco_rank,country,vertical,psl_version,added_on
example.com,"head|news",4213,US,news,2026-09-01,2026-09-08
```

### Acceptance criteria

- Re-running `build_panel.py` with the same pinned sources and seed produces a byte-identical CSV.
- Every domain is a valid registrable domain under the pinned PSL; no subdomains, no IPs, no punycode inconsistency (store as A-label, i.e. `xn--`).
- Manifest records: every source URL, its retrieval date, its checksum, the PSL version, the RNG seed.
- Panel is immutable once published. Corrections ship as `panel-2026Q4.1` with a documented diff.

---

## 3. WP1 — Fetcher

*Go 1.23 · 8–12 days · the only component with a hard daily deadline*

### 3.1 Job shape

One binary, one run per day, sharded across N goroutine pools. For each `(domain, resource)` pair it makes at most one successful fetch per run.

Resources, fetched in this order per domain:

| Resource key | Path | Size cap | Notes |
|---|---|---|---|
| `robots_txt` | `/robots.txt` | 1 MiB | Primary. Also yields declared `Sitemap:` URLs. |
| `llms_txt` | `/llms.txt` | 2 MiB | Expect 404 for most domains — that is a fact, record it. |
| `sitemap_xml` | `/sitemap.xml` | 10 MiB | Top-level only. Never follow children in v1. |

Volume: ~1.08M domains × 3 = **~3.25M requests/run**. Over a 6-hour window that is ~150 req/s sustained. This is modest; do not over-engineer for throughput. Correctness and politeness are the hard requirements.

### 3.2 HTTP client policy

```
User-Agent: CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)
Accept:     text/plain, text/markdown, application/xml, */*
Accept-Encoding: gzip
```

The `+https://` URL **must** resolve to a live page before the first production run, stating who we are, what we fetch, how often, and how to be excluded. Non-negotiable.

- **Scheme**: HTTPS first. On TLS or connection failure, retry once over HTTP. Record which succeeded.
- **Timeouts**: 5 s connect, 10 s TLS handshake, 15 s total per request. Hard.
- **Redirects**: follow up to 3. Record `url_final`, `redirect_count`, and `crossed_registrable_domain`. Do **not** treat a cross-domain redirect as failure — delegating robots.txt to a CDN host is legitimate — but flag it so the parser and analysts can see it.
- **Retries**: one retry on `429`, `503`, and network errors, after a 30–90 s jittered delay. Never more. A domain that fails twice is recorded as failed and retried tomorrow.
- **Politeness limits**, all configurable:
  - max 1 in-flight request per host
  - max 4 concurrent per resolved IP
  - max 20 concurrent per ASN
  - global token bucket, default 200 req/s, burst 400
- **Body handling**: stream with a hard byte cap. On exceeding the cap, keep the first N bytes and set `truncated: true`. Never buffer an unbounded response.
- **Compression bombs**: cap decompressed size at 4× the byte cap, then abort with `outcome: too_large`.

### 3.3 Scheduling and sharding

- Shard key `fnv32(domain) % shard_count`. Deterministic, so a domain lands in roughly the same time slot each day — this keeps per-domain observation intervals even, which matters for change detection.
- Run window opens 02:00 UTC. Each shard jitters its start within the window.
- Run identity: `(panel_version, run_date, fetcher_version)`.
- **Idempotent resume**: on restart, read the run manifest and skip `(domain, resource)` pairs already recorded. A crashed run is resumed, never restarted.

### 3.4 Output — two streams

**Stream A: content blobs (deduplicated).** Written only when the SHA-256 is not already present in the blob index.

```
r2://cpi-raw/blob/<sha256[0:2]>/<sha256[2:4]>/<sha256>.gz
```

After the first full run, expect **<1% of domains to produce a new blob on any given day**. This is what makes the whole project affordable — a change in content hash is also the only trigger for re-parsing downstream.

**Stream B: fetch observations (one record per attempt, always written).**

```
r2://cpi-obs/dt=<run_date>/resource=<key>/part-<shard>-<seq>.ndjson.zst
```

```json
{
  "panel_version": "2026Q4",
  "run_date": "2026-09-08",
  "domain": "example.com",
  "resource": "robots_txt",
  "fetched_at": "2026-09-08T02:14:07.412Z",
  "url_requested": "https://example.com/robots.txt",
  "url_final": "https://www.example.com/robots.txt",
  "redirect_count": 1,
  "crossed_registrable_domain": false,
  "scheme_used": "https",
  "http_status": 200,
  "outcome": "ok",
  "content_sha256": "9f2b…",
  "content_length": 1843,
  "content_type": "text/plain; charset=utf-8",
  "content_encoding": "gzip",
  "truncated": false,
  "latency_ms": 312,
  "blob_written": false,
  "fetcher_version": "1.0.3",
  "error_detail": null
}
```

### 3.5 Outcome enum — closed set, never extend without a migration

`ok` · `not_found` (404/410) · `forbidden` (401/403) · `server_error` (5xx) · `rate_limited` (429 after retry) · `timeout` · `dns_error` · `tls_error` · `conn_refused` · `too_large` · `empty_body` · `redirect_loop` · `invalid_url`

Failures are data, not exceptions. A domain going `ok → forbidden` is itself a signal worth charting.

### 3.6 Run manifest and gap report

Every run writes `r2://cpi-obs/manifest/<run_date>.json`:

```json
{
  "run_date": "2026-09-08",
  "panel_version": "2026Q4",
  "fetcher_version": "1.0.3",
  "started_at": "...", "finished_at": "...",
  "domains_in_panel": 1083412,
  "attempted": 3250236,
  "by_outcome": { "ok": 2981204, "not_found": 210417, "timeout": 3122, "...": 0 },
  "blobs_written": 9841,
  "unexplained_failure_rate": 0.0021,
  "complete": true
}
```

`unexplained_failure_rate` counts `timeout + dns_error + tls_error + conn_refused + rate_limited` over `attempted`. A `404` is fully explained and does not count.

### 3.7 Acceptance criteria — WP1

1. A full panel pass completes in **under 6 hours** on a single 8-vCPU host, with `unexplained_failure_rate < 0.5%`.
2. Killing the process at any point and restarting produces the same final observation set as an uninterrupted run (verified by a chaos test that SIGKILLs at 30% and 70%).
3. Re-running a completed run writes zero new observations and zero new blobs.
4. Politeness limits are provably enforced: a test against a local server asserts never more than one in-flight request per host.
5. Every one of the 13 outcome values is reachable and covered by an integration test against a mock server.
6. Memory stays under 2 GB at peak with 2,000 workers (no unbounded body buffering).
7. `blob_written: false` for ≥99% of records on the second consecutive identical run.

---

## 4. WP2 — Parser

*Python 3.12 · 10–14 days · hire the most careful person available for this*

This package decides every number we publish. A silent misclassification here becomes a false headline, and a publicly corrected false headline destroys more credibility than a quarter of collection builds.

### 4.1 The gate — is this actually robots.txt?

**This is the single highest-risk function in the codebase.** A large share of hosts answer `/robots.txt` with an HTTP 200 and an HTML soft-404 page. A naive parser finds no directives, concludes "no rules", and reports the site as *allowing every AI crawler*. Get this wrong and every headline number is inflated.

`detect.classify(body, content_type) -> Verdict` returns one of:

- `robots` — proceed to parse
- `not_robots_html` — body matches `<!doctype`, `<html`, `<head`, or `<body` in the first 2 KiB (case-insensitive), or content-type is `text/html` **and** no line matches a known directive
- `not_robots_binary` — >2% of bytes in the first 8 KiB are non-printable, non-whitespace
- `empty` — zero bytes, or only whitespace and comments
- `ambiguous` — no directive lines matched but the body is small, plain text and non-HTML

**Rule: `ambiguous` is excluded from all published aggregates.** Flag it, count it, chart the rate, but never fold it into a percentage. Guessing here is how we lose.

### 4.2 robots.txt parsing rules

Follow **RFC 9309**, resolving ambiguities the way Google's reference implementation does, because that is what site owners actually test against.

1. **Encoding** — strip UTF-8/UTF-16 BOM. Decode as UTF-8 with `errors="replace"`. Split lines on `\r\n`, `\n`, or bare `\r`.
2. **Parse cap** — parse only the first **500 KiB** (Google's documented limit). Set `truncated_for_parse` if the body exceeded it.
3. **Lines** — strip everything from the first `#`. Trim whitespace. Split on the first `:`. Directive names are case-insensitive; values are not.
4. **Grouping** — consecutive `User-agent` lines start or extend a group. A group ends when a `User-agent` line follows a non-`User-agent` directive. **Blank lines and comment-only lines do not end a group** — this is the most commonly mis-implemented rule in the spec.
5. **Duplicate groups** — if the same user-agent token appears in multiple groups, **merge their rules**. Do not take first or last.
6. **Agent matching** — case-insensitive match of the registry's `ua_token` against the group's user-agent value. Exact token match, not substring: a group for `Googlebot-Image` must not match `Googlebot`. Longest matching token wins. If no token matches, fall back to the `*` group.
7. **Path rules** — `Allow` and `Disallow`. Percent-decode both rule and test path except for `%2F`. Support `*` (any sequence) and `$` (end anchor); compile to regex once per group and cache.
8. **Precedence** — longest matching rule wins. On equal length, **`Allow` beats `Disallow`**.
9. **Empty values** — `Disallow:` with an empty value means allow everything. `Allow:` with an empty value is ignored.
10. **Non-standard directives** — capture `Crawl-delay`, `Request-rate`, `Visit-time`, `Sitemap`, and any unrecognised key into an `extras` map. `Sitemap` is global, not group-scoped.

### 4.3 State derivation — refines the four-state model in the brief

The brief's four states conflated two independent facts. Split them:

**`state`** — the effective verdict for this agent:

| Value | Definition |
|---|---|
| `ALLOWED` | The effective group contains no `Disallow` rule with a non-empty value. |
| `BLOCKED` | `Disallow: /` is effective for path `/` with no longer `Allow` override. |
| `PARTIAL` | `/` is allowed but at least one non-empty `Disallow` rule exists. |

**`rule_source`** — where that verdict came from:

| Value | Definition |
|---|---|
| `EXPLICIT` | A group names this agent's token directly. |
| `WILDCARD` | No group names it; the `*` group applied. |
| `NONE` | No group applies at all — no named group and no `*` group. Treated as `ALLOWED` / `NONE`. |

This split is what lets us make the claim nobody else makes. "41% of news sites block GPTBot" is a different and far more interesting statement when you can say **how many of those did it deliberately** (`EXPLICIT`) versus inherited it from a blanket `*` rule. Every published figure must state which `rule_source` values it includes.

### 4.4 llms.txt and sitemap parsing

`llmstxt.py` — structural only, no semantics: present/absent, byte length, whether it parses as Markdown, H1 present, section count, link count, whether links resolve to same registrable domain. We report adoption honestly; per Ahrefs' 137k-domain study 97% of these files are never fetched by anyone, so this is a secondary metric and must never carry a headline.

`sitemap.py` — top-level only: root element (`sitemapindex` | `urlset` | `invalid`), count of direct children, min/max `lastmod`, whether `lastmod` is present on ≥50% of entries, and whether the sitemap was declared in robots.txt. **Do not fetch child sitemaps.** Stream the XML with `lxml.etree.iterparse` and abort at 10 MiB.

### 4.5 Testing — the acceptance bar

Three independent harnesses, all required:

**1. Golden corpus** — `tests/corpus/`, 500 hand-built cases with expected JSON. Must include at minimum:

- HTML soft-404 served as robots.txt (several shapes: WordPress, Cloudflare, IIS, generic)
- blank lines inside a group; comments inside a group
- the same user-agent in two separate groups
- `Disallow` with no value; `Allow` with no value
- conflicting rules of equal length
- `*` and `$` wildcards, including `/*.pdf$`
- `Disallow:/` with no space; mixed case directives; `USER-AGENT:`
- UTF-8 BOM, UTF-16 BOM, Latin-1 bytes, embedded NULs
- a 2 MiB file (parse-cap behaviour)
- CRLF, bare CR, and mixed line endings
- a file that is only `Sitemap:` lines
- non-ASCII user-agent tokens
- real-world captures from 20 major publishers, checked in verbatim

**2. Differential test** — run a 10,000-file random sample through both our parser and a reference implementation (Google's `robotstxt` via bindings, or `protego` as a secondary check) for a fixed probe-path set. **Every disagreement opens a ticket and must be resolved as either a fixed bug or a documented, justified deviation.** Zero unexplained disagreements at acceptance.

**3. Human audit** — 300 domains sampled stratified by outcome, classified by hand, compared against parser output. **Required: ≥98% agreement on `state`, ≥99% on the `detect` gate.** The gate matters more than the parse: a gate error corrupts aggregates silently, a parse error usually shows up as an obvious outlier.

### 4.6 Versioning

Every parse writes `parse_version` (semver of the parser package). A parser change that could alter any output bumps the minor version and triggers a **full re-parse from stored blobs** — which is cheap and is the entire reason invariant 2 exists. Re-parses are additive: never delete old parse rows, mark them superseded.

---

## 5. WP3 — Wayback backfill

*Python · 5–7 days · runs as a slow background job through all of Phase 1*

Turns a three-month-old project into a four-year dataset. Highest value-per-day in the plan.

### 5.1 Method

For each of the top 50,000 domains by Tranco rank:

**Step 1 — enumerate captures** via the CDX API:

```
https://web.archive.org/cdx/search/cdx
  ?url=example.com/robots.txt
  &output=json
  &fl=timestamp,digest,statuscode,length,mimetype
  &filter=statuscode:200
  &collapse=digest
  &from=20220101
```

`collapse=digest` returns only captures where content *changed* — precisely our unit of interest, and it cuts volume by an order of magnitude.

**Step 2 — select** the capture nearest each quarter boundary from 2022Q1 onward, plus every capture where the digest differs from the previously selected one. Cap at 40 captures per domain.

**Step 3 — fetch content** using the `id_` modifier, which returns the original bytes without Wayback's HTML wrapper:

```
https://web.archive.org/web/<timestamp>id_/http://example.com/robots.txt
```

Omitting `id_` returns a rewritten HTML page — it will parse as garbage and silently poison the dataset. Assert on the first request of every batch that the response is not HTML.

**Step 4** — run through the WP2 parser exactly as live data. Emit `policy_interval` rows with `provenance = 'wayback'` and `observed_at` set to the capture timestamp.

### 5.2 Politeness — treat this as a hard constraint

The Internet Archive is a public good and is not obliged to serve us.

- **1 request per second, single worker, no parallelism.** Do not tune this up.
- Exponential backoff on 429/503, starting at 60 s, max 30 min, unlimited retries.
- Checkpoint after every domain; the job must survive being stopped for a week and resumed.
- Identify with the same User-Agent and contact URL as the fetcher.
- Estimated volume: 50k domains × ~16 captures ≈ 800k requests ≈ 9–10 days of continuous running. That is fine. It runs in the background while WP2 and WP4 proceed.

### 5.3 Acceptance criteria

1. ≥60% of the top 50k domains have ≥8 distinct quarterly observations since 2022-01-01.
2. Backfilled rows are schema-identical to live rows and distinguishable **only** by `provenance`.
3. Zero HTML-wrapper contamination: a check asserts every fetched body passes `detect.classify` as `robots` or a legitimate non-robots verdict, never as a Wayback chrome page.
4. Job resumes correctly from checkpoint after a 24-hour interruption, verified by test.
5. Sustained request rate never exceeds 1.2 req/s, measured over any 60-second window.

---

## 6. WP4 — Warehouse

*PostgreSQL 16 + Python · 4–6 days · see `warehouse/migrations/0001_init.sql`*

### 6.1 The critical modelling decision

The naive design — one state row per `(domain, agent, day)` — produces **1.08M × 60 agents × 365 days ≈ 23 billion rows per year**. That is unaffordable and unnecessary.

Two changes collapse it by four orders of magnitude:

**(a) Interval storage, not daily snapshots.** Robots.txt files change rarely. Store validity intervals (SCD type 2), writing a new row only when state actually changes:

```sql
policy_interval(domain, agent_slug, valid_from, valid_to, state, rule_source, ...)
```

Point-in-time query:

```sql
WHERE valid_from <= :d AND (valid_to IS NULL OR valid_to > :d)
```

**(b) Materialise explicit rules only.** Do not store 60 agent rows for a domain whose robots.txt names none of them. Store:

- `policy_interval` — rows only where `rule_source = 'EXPLICIT'`
- `wildcard_interval` — one row per domain per `*`-group change

Then resolve effective state for any `(domain, agent)` pair in a view: explicit row if present, else the wildcard row, else `ALLOWED`/`NONE`. Real-world result: **~2–4M rows in total**, comfortable for a 4 GB Postgres instance.

### 6.2 Derivation trigger

**Only re-parse and re-derive when `content_sha256` changes for a `(domain, resource)` pair.** The daily pipeline is therefore:

```
load observations (COPY)
  → find (domain, resource) pairs whose hash differs from their latest known hash
  → fetch those blobs from R2  [~1% of panel]
  → parse
  → close open intervals whose state changed, open new ones
  → emit policy_event rows
  → refresh rollups
```

Target: **under 20 minutes end to end** on a normal day.

### 6.3 Events

Every interval transition writes a `policy_event` — this table is the product's most quotable output. Event types: `first_seen`, `blocked`, `unblocked`, `tightened` (ALLOWED→PARTIAL, PARTIAL→BLOCKED), `loosened`, `agent_named` (first time a domain mentions this agent explicitly), `agent_unnamed`, `file_removed`, `file_appeared`.

"Fourteen of the top 50 UK news sites started explicitly blocking Meta's crawler in the same week" is a `policy_event` query. Design for it.

### 6.4 Rollups

One SQL file per published view in `warehouse/rollups/`, each with a header comment stating the exact claim it supports and the panel/parse versions it assumes. Materialised views, refreshed after each derive:

- `mv_state_by_day_agent` — day × agent × state → domain count
- `mv_state_by_day_agent_country`
- `mv_state_by_day_agent_vertical`
- `mv_state_by_operator_purpose` — the training-vs-search story
- `mv_divergence` — domains blocking training but allowing search, by day
- `mv_events_weekly`
- `mv_llmstxt_adoption`
- `mv_sitemap_presence`

**Rule: the site may only read from materialised views, never from base tables.** If a number is on the site, there is a named view behind it, and `docs/methodology.md` names that view.

### 6.5 Acceptance criteria

1. Full rollup rebuild from base tables completes in **under 15 minutes**.
2. Daily incremental derive completes in **under 20 minutes**.
3. Every published figure traces to exactly one materialised view, asserted by a test that greps the site source for hardcoded numbers and fails on any hit.
4. A full re-parse of all blobs at a new `parse_version` is a single command and does not mutate or delete prior rows.
5. Point-in-time query for any past date returns results identical to what that date's snapshot would have produced (verified against a retained 3-day sample of daily snapshots).

---

## 7. WP5 — Public tracker site

*Astro · 8–12 days · statically generated, no client-side data fetching*

### 7.1 Pages

| Route | Content |
|---|---|
| `/` | Headline figures, the training-vs-search divergence chart, biggest movers this week |
| `/domain/[domain]` | One domain's full policy timeline, per agent, with the raw robots.txt at each change point |
| `/agent/[slug]` | One agent: adoption of blocking over time, by country and vertical |
| `/operator/[slug]` | An operator's agents side by side — where OpenAI is blocked for training but allowed for search |
| `/country/[cc]`, `/vertical/[slug]` | League tables |
| `/events` | Reverse-chronological feed of policy changes, filterable |
| `/methodology` | Panel construction, parse rules, known limitations, changelog |
| `/data` | CSV downloads per view, plus the panel file and its checksum |

### 7.2 Rendering rules

- **Charts are SVG generated at build time in Python**, written to disk, inlined into the page. Zero client-side charting JS. Three reasons: Lighthouse stays at 100, charts are screenshot-able for press, and pages work with JS disabled.
- Every chart carries its own caption, axis labels naming values the chart actually reaches, source line, panel version and date — so it stands alone when lifted into a news article.
- Every chart has a sibling CSV download of exactly the data it plots.
- Theme-aware: chart colours come from CSS custom properties, readable in light and dark.
- Domain pages are pre-rendered for the top 100k; the long tail renders on demand via a single edge function reading a static JSON index.

### 7.3 Acceptance criteria

1. Builds from the warehouse in CI, on a schedule, with no manual step.
2. Lighthouse ≥95 on performance and accessibility for `/`, a domain page and an agent page.
3. Core tables and figures render with JavaScript disabled.
4. Every chart has a matching CSV, verified by a build-time assertion that fails the build if one is missing.
5. `/methodology` is complete enough that an outside researcher can reproduce a headline figure from the published panel file and the documented view definition. **Test this on a real person before launch.**

---

## 8. WP6 — Launch report

*4–6 days · web-first document plus print-quality PDF*

One genuinely novel finding, not a listicle. Leading candidates, to be chosen from the data:

1. **The training/search split.** How many sites now discriminate between an operator's training crawler and its search crawler — and how that has grown since 2022. This is the finding only we can produce, because it requires the `rule_source` + `purpose` model.
2. **The Cloudflare default effect.** Do domains first seen after the 2026 default-blocking change show materially different policy from comparable older domains?
3. **Churn.** Which verticals keep changing their minds, and in which direction.

Constraint on every chart in the report: **it must state its own claim when lifted alone into an article.** That is how these travel.

---

## 9. Configuration

Single YAML per environment, no config in code, no secrets in the repo (use environment variables or a secret store).

```yaml
panel:
  version: "2026Q4"
  path: "s3://cpi-panel/panel-2026Q4.csv"

fetcher:
  resources: [robots_txt, llms_txt, sitemap_xml]
  window_start_utc: "02:00"
  window_hours: 6
  shards: 16
  workers_per_shard: 128
  global_rate_limit_rps: 200
  per_host_inflight: 1
  per_ip_concurrent: 4
  per_asn_concurrent: 20
  timeouts: { connect_s: 5, tls_s: 10, total_s: 15 }
  max_redirects: 3
  size_caps_bytes: { robots_txt: 1048576, llms_txt: 2097152, sitemap_xml: 10485760 }
  retry: { attempts: 1, backoff_s: [30, 90] }
  user_agent: "CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)"

parser:
  version: "1.0.0"
  parse_cap_bytes: 512000
  probe_paths: ["/", "/index.html", "/article/example", "/products/example", "/blog/example"]

backfill:
  rate_limit_rps: 1.0
  from_date: "2022-01-01"
  domains_top_n: 50000
  max_captures_per_domain: 40
```

---

## 10. Operations

### Schedule

| Job | Cadence | Window |
|---|---|---|
| Fetch run | Daily | 02:00–08:00 UTC |
| Load + derive + rollups | Daily | 08:30 UTC |
| Site rebuild | Daily | 09:30 UTC |
| Wayback backfill | Continuous | Phase 1 only, then monthly top-up |
| Panel rebuild | Quarterly | Manual, reviewed |

### Alerts — page on these

1. Fetch run not `complete: true` by 09:00 UTC.
2. `unexplained_failure_rate` > 0.5%, or > 2× the trailing 7-day median.
3. Derive step failed, or ran past 30 minutes.
4. **`detect` gate distribution shifted more than 3 percentage points day over day.** This is the parser-corruption canary and the most valuable alert in the system — it catches the failure mode that would otherwise reach publication.
5. `blobs_written` > 5% of panel in one day (either a real event worth writing about, or a hashing bug — check which).
6. Site build failed.

### Cost envelope

| Component | Choice | $/mo |
|---|---|---|
| Fetch worker | Hetzner CPX41, 8 vCPU | 55 |
| Blob + observation storage | Cloudflare R2, gzip + zstd, hash-deduped | 25 |
| Warehouse | Managed Postgres, 4 GB | 60 |
| Site | Cloudflare Pages | 0 |
| Panel sources | Tranco, CT logs, Wayback CDX | 0 |
| Domain, email, monitoring | — | 40 |
| **Total** | | **~180** |

---

## 11. Conduct and compliance

Not optional, and not merely ethical — the project's credibility is its only asset in phase one.

- Honest User-Agent with a live contact URL, from the first production request.
- Publish `/bot` before launching: what we fetch, how often, from which IPs, how to be excluded.
- Honour any exclusion request within 24 hours; keep a documented, auditable removal log.
- Publish **derived facts and short excerpts with links to source**, not wholesale copies of others' files.
- No personal data enters the system. If any is ever found in a fetched file, it is purged, not analysed.
- Conservative concurrency by default. If in doubt, slow down — we have a 6-hour window for a 40-minute job.

---

## 12. Definition of done — day 90

- [ ] 90 consecutive daily runs, zero unexplained gaps, provable from manifests
- [ ] Multi-year reconstructed history for ≥60% of the top 50k domains
- [ ] Parser at ≥98% human-audit agreement, zero unexplained differential disagreements
- [ ] Tracker live; a stranger reproduces a headline figure from `/methodology` alone
- [ ] Report published with ≥5 external referring publications
- [ ] 20 customer conversations completed, ≥3 concrete "I would pay for X"

The last item is the one that decides whether the project continues. The first is the one that cannot be recovered if missed.
