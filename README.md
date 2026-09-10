# Crawl Policy Index

A longitudinal record of which AI crawlers every significant website allows, blocks, or restricts.

Three text files per domain per day — `robots.txt`, `llms.txt`, `sitemap.xml` — stored immutably, parsed into policy intervals, reconstructed back to 2022 from the Internet Archive, and published as a free tracker.

**Read [`SPEC.md`](./SPEC.md) before writing any code.** It is the contract. This file is only how to get a machine running.

---

## The three invariants

Any design decision that conflicts with one of these loses the argument.

1. **No missing days.** A day not collected is unrecoverable. The fetcher degrades; it does not stop.
2. **Raw bytes are immutable and permanent.** Every parse is reproducible from stored blobs. Parser bugs are always fixable retroactively — but only because we never discard input.
3. **No published number without a traceable derivation.** Every figure resolves to one SQL view over one parse version over one panel version.

---

## Work packages

Independently scopeable and independently testable. Acceptance criteria for each are in `SPEC.md`.

| WP | Component | Lang | Days | Depends on |
|----|-----------|------|------|-----------|
| WP0 | Panel construction | Python | 3–4 | — |
| WP1 | Fetcher | **Go 1.23** | 8–12 | WP0 |
| WP2 | robots.txt parser | Python 3.12 | 10–14 | — (works on stored blobs) |
| WP3 | Wayback backfill | Python 3.12 | 5–7 | WP2 |
| WP4 | Warehouse + rollups | SQL / Python | 4–6 | WP2 |
| WP5 | Public tracker site | Astro | 8–12 | WP4 |
| WP6 | Launch report | — | 4–6 | WP4 |

**Commission WP1 and WP2 first.** WP1 because invariant 1 has a deadline that starts today; WP2 because it is the correctness-critical package and its lead time is longest. WP2 does not block on WP1 — it operates on stored blobs, so it can be developed against the test corpus in parallel.

Do not commission WP5 until the data has proven worth showing.

---

## Local setup

```bash
git clone <repo> && cd crawl-policy-index
make dev-up            # Postgres 16 + MinIO (S3-compatible stand-in for R2)
make migrate           # applies warehouse/migrations/*.sql in order
make test              # Go tests + pytest + the golden corpus
```

### Build a development panel

Never develop against the full 1.08M-domain panel. Use a 5,000-domain sample:

```bash
python panel/build_panel.py --version dev --sample 5000 --seed 42
```

Deterministic, so everyone's dev panel is identical.

### Run the fetcher locally

```bash
cd fetcher
go run ./cmd/cpifetch \
    --config ../config/dev.yml \
    --panel  ../data/panel-dev.csv \
    --once
```

`--once` runs a single pass and exits. Without it the binary waits for its scheduled window.

### Parse stored blobs

```bash
python -m cpi_parser.cli reparse --resource robots_txt --since 2026-09-01
```

Reads from blob storage, writes intervals and events. Safe to re-run — it is idempotent per `(blob, parse_version)`.

---

## The two things most likely to go wrong

Both are called out in `SPEC.md`, but they are worth repeating where someone will actually see them.

### 1. HTML pages served as `robots.txt`

A large share of hosts answer `/robots.txt` with HTTP 200 and an HTML error page. A naive parser finds no directives, concludes "no rules", and records the site as **allowing every AI crawler**. Do that across a million domains and every headline number is inflated.

`cpi_parser.detect.classify()` is the gate. It is the highest-risk function in the codebase. Its output distribution is monitored daily and alerted on at a 3-percentage-point day-over-day shift — that alert is the parser-corruption canary and it exists specifically to catch this failure mode before it reaches publication.

Rows classified `ambiguous` are excluded from every published aggregate. Never fold them into a percentage; guessing is how the project loses its only asset.

### 2. Storing daily snapshots instead of intervals

One row per `(domain, agent, day)` is ~23 billion rows per year. Policy is stored as **SCD-2 intervals**, and only for agents a domain names **explicitly** — everything else resolves from `wildcard_interval` through `effective_policy()`. Total is 2–4M rows.

Corollary that makes the whole system cheap: **re-parse only when `content_sha256` changes.** After the first full run, under 1% of the panel produces a new blob on any given day.

---

## Politeness is a hard requirement, not a nicety

We are a crawler that measures crawler policy. Being a badly-behaved crawler would be both self-defeating and embarrassing.

- Honest `User-Agent` with a contact URL, from the very first production request.
- `https://crawlpolicyindex.org/bot` **must be live before the first production run** — who we are, what we fetch, how often, from which IPs, and how to be excluded.
- One in-flight request per host. Ever.
- The Wayback backfill runs at **1 req/s, single worker**. Do not tune this up. The Internet Archive is a public good and is under no obligation to serve us.
- Exclusion requests honoured within 24 hours, with an auditable log.

Fetching `robots.txt` is the most defensible request on the web — but only if we behave like it.

---

## Repository layout

```
registry/agents.yml      Agent registry — source of truth. Every entry ships
                         verified:false and is excluded from published figures
                         until a human checks it against operator docs.
panel/                   WP0 — deterministic panel construction
fetcher/                 WP1 — Go
parser/                  WP2 — Python, + tests/corpus (500 golden cases)
backfill/                WP3 — Internet Archive reconstruction
warehouse/               WP4 — migrations, loaders, rollups
site/                    WP5 — Astro, build-time SVG charts, zero client JS
report/                  WP6
docs/methodology.md      Public. The page researchers will judge us on.
docs/runbook.md          On-call: what each alert means, how to recover.
docs/decisions/          ADRs — one file per irreversible choice.
```

---

## Day-90 definition of done

- [ ] 90 consecutive daily runs, zero unexplained gaps, provable from run manifests
- [ ] Multi-year history reconstructed for ≥60% of the top 50k domains
- [ ] Parser at ≥98% human-audit agreement; zero unexplained differential disagreements
- [ ] Tracker live; a stranger reproduces a headline figure from `/methodology` alone
- [ ] Report published, ≥5 external referring publications
- [ ] 20 customer conversations, ≥3 concrete "I would pay for X"

The last item decides whether the project continues. The first is the only one that cannot be recovered if missed.
