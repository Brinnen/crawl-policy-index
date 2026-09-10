-- =====================================================================
-- Crawl Policy Index — warehouse schema
-- migration 0001_init.sql  ·  PostgreSQL 16  ·  forward-only
--
-- Design notes that matter before you read the DDL:
--
--  1. Policy is stored as INTERVALS, not daily snapshots. A naive
--     (domain, agent, day) table is ~23 billion rows/year. Intervals
--     plus explicit-only materialisation give ~2-4M rows total.
--
--  2. Only EXPLICIT agent rules live in policy_interval. If a domain's
--     robots.txt does not name an agent, its state is resolved from
--     wildcard_interval at query time by v_effective_policy.
--
--  3. Nothing is ever deleted. Re-parses are additive and versioned.
--     Raw blobs in R2 are the immutable source of truth; every row
--     here is reproducible from them.
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------
-- Enums — closed sets. Extending any of these is a migration, not a
-- config change, because published figures depend on their cardinality.
-- ---------------------------------------------------------------------

CREATE TYPE resource_kind AS ENUM ('robots_txt', 'llms_txt', 'sitemap_xml');

CREATE TYPE fetch_outcome AS ENUM (
    'ok', 'not_found', 'forbidden', 'server_error', 'rate_limited',
    'timeout', 'dns_error', 'tls_error', 'conn_refused',
    'too_large', 'empty_body', 'redirect_loop', 'invalid_url'
);

-- Result of detect.classify(). 'ambiguous' rows are EXCLUDED from every
-- published aggregate — see SPEC 4.1. Never fold them into a percentage.
CREATE TYPE detect_verdict AS ENUM (
    'robots', 'not_robots_html', 'not_robots_binary', 'empty', 'ambiguous'
);

CREATE TYPE policy_state AS ENUM ('ALLOWED', 'BLOCKED', 'PARTIAL');

-- Where the verdict came from. The EXPLICIT/WILDCARD split is the
-- distinction no competing dataset makes; guard it carefully.
CREATE TYPE rule_source AS ENUM ('EXPLICIT', 'WILDCARD', 'NONE');

CREATE TYPE agent_purpose AS ENUM (
    'training',        -- crawls to build a training corpus
    'search_index',    -- builds a retrieval index for an AI search product
    'user_fetch',      -- fetches a URL on demand, in response to a user action
    'agentic',         -- autonomous browsing agent
    'opt_out_token',   -- not a crawler; a token honoured for opt-out (Google-Extended)
    'unknown'
);

CREATE TYPE provenance AS ENUM ('live', 'wayback');

CREATE TYPE event_kind AS ENUM (
    'first_seen', 'blocked', 'unblocked', 'tightened', 'loosened',
    'agent_named', 'agent_unnamed', 'file_removed', 'file_appeared'
);


-- ---------------------------------------------------------------------
-- Panel — frozen and versioned. Every published statistic is "of panel X".
-- ---------------------------------------------------------------------

CREATE TABLE panel_version (
    version         text PRIMARY KEY,              -- '2026Q4'
    frozen_on       date        NOT NULL,
    psl_version     text        NOT NULL,          -- Public Suffix List snapshot
    tranco_list_id  text        NOT NULL,          -- pinned, never 'latest'
    rng_seed        bigint      NOT NULL,
    domain_count    integer     NOT NULL,
    manifest        jsonb       NOT NULL,          -- every source URL + checksum
    checksum_sha256 text        NOT NULL
);

CREATE TABLE panel_domain (
    panel_version  text    NOT NULL REFERENCES panel_version(version),
    domain         text    NOT NULL,               -- registrable domain, A-label
    strata         text[]  NOT NULL,               -- {head,news,nordic,tail}
    tranco_rank    integer,
    country        char(2),
    vertical       text,
    added_on       date    NOT NULL,
    PRIMARY KEY (panel_version, domain)
);

CREATE INDEX idx_panel_domain_country  ON panel_domain (panel_version, country);
CREATE INDEX idx_panel_domain_vertical ON panel_domain (panel_version, vertical);
CREATE INDEX idx_panel_domain_strata   ON panel_domain USING gin (strata);
CREATE INDEX idx_panel_domain_trgm     ON panel_domain USING gin (domain gin_trgm_ops);


-- ---------------------------------------------------------------------
-- Agent registry — source of truth is registry/agents.yml, loaded here.
-- Never edit this table by hand; change the YAML and re-run the loader.
-- ---------------------------------------------------------------------

CREATE TABLE agent (
    slug            text PRIMARY KEY,              -- 'openai-gptbot'
    ua_token        text        NOT NULL UNIQUE,   -- 'GPTBot', matched case-insensitively
    display_name    text        NOT NULL,
    operator        text        NOT NULL,
    purpose         agent_purpose NOT NULL,
    documented_url  text,                          -- operator's own documentation
    verified        boolean     NOT NULL DEFAULT false,
    first_seen_on   date,
    active          boolean     NOT NULL DEFAULT true,
    notes           text
);

CREATE INDEX idx_agent_operator ON agent (operator, purpose);

COMMENT ON COLUMN agent.verified IS
    'True only when ua_token has been confirmed against the operator''s own
     published documentation. Unverified agents MUST be excluded from all
     published figures.';


-- ---------------------------------------------------------------------
-- Fetch layer — one row per attempt, always written, including failures.
-- Failures are data: a domain going ok -> forbidden is a real signal.
-- ---------------------------------------------------------------------

CREATE TABLE fetch_observation (
    id                bigint GENERATED ALWAYS AS IDENTITY,
    domain            text          NOT NULL,
    resource          resource_kind NOT NULL,
    run_date          date          NOT NULL,
    prov              provenance    NOT NULL DEFAULT 'live',
    fetched_at        timestamptz   NOT NULL,
    url_requested     text          NOT NULL,
    url_final         text,
    redirect_count    smallint      NOT NULL DEFAULT 0,
    crossed_reg_domain boolean      NOT NULL DEFAULT false,
    scheme_used       text,
    http_status       smallint,
    outcome           fetch_outcome NOT NULL,
    content_sha256    char(64),
    content_length    integer,
    content_type      text,
    truncated         boolean       NOT NULL DEFAULT false,
    latency_ms        integer,
    fetcher_version   text          NOT NULL,
    panel_version     text          NOT NULL,
    error_detail      text,
    PRIMARY KEY (id, run_date)
) PARTITION BY RANGE (run_date);

-- Create partitions monthly; automate in warehouse/migrations/partitions.py
CREATE TABLE fetch_observation_2026m09 PARTITION OF fetch_observation
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

CREATE UNIQUE INDEX idx_fetchobs_unique
    ON fetch_observation (domain, resource, run_date, prov);
CREATE INDEX idx_fetchobs_hash    ON fetch_observation (content_sha256)
    WHERE content_sha256 IS NOT NULL;
CREATE INDEX idx_fetchobs_outcome ON fetch_observation (run_date, resource, outcome);


-- Content blobs. One row per unique SHA-256 ever seen, across all domains.
-- Expect <1% of the panel to produce a new blob on a normal day; that
-- ratio is the project's core economics and is alerted on.
CREATE TABLE content_blob (
    sha256          char(64) PRIMARY KEY,
    resource        resource_kind NOT NULL,
    byte_len        integer     NOT NULL,
    storage_key     text        NOT NULL,          -- r2://cpi-raw/blob/9f/2b/9f2b….gz
    first_seen_on   date        NOT NULL,
    last_seen_on    date        NOT NULL,
    seen_count      bigint      NOT NULL DEFAULT 1,
    detect_result   detect_verdict,
    parse_version   text,
    parsed_at       timestamptz,
    parse_error     text
);

CREATE INDEX idx_blob_unparsed ON content_blob (resource, parse_version)
    WHERE parse_version IS NULL;
CREATE INDEX idx_blob_detect   ON content_blob (first_seen_on, detect_result);


-- ---------------------------------------------------------------------
-- Policy layer — SCD-2 intervals. valid_to IS NULL means "still current".
-- ---------------------------------------------------------------------

-- Explicit agent rules ONLY. A domain that never names GPTBot has no row
-- here for it; v_effective_policy resolves that from wildcard_interval.
CREATE TABLE policy_interval (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    domain          text          NOT NULL,
    agent_slug      text          NOT NULL REFERENCES agent(slug),
    valid_from      date          NOT NULL,
    valid_to        date,                          -- NULL = open interval
    state           policy_state  NOT NULL,
    matched_ua_token text         NOT NULL,        -- what the file literally said
    crawl_delay_s   numeric(8,2),
    content_sha256  char(64)      NOT NULL REFERENCES content_blob(sha256),
    parse_version   text          NOT NULL,
    prov            provenance    NOT NULL DEFAULT 'live',
    CONSTRAINT chk_interval_order CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE INDEX idx_polint_lookup  ON policy_interval (domain, agent_slug, valid_from DESC);
CREATE INDEX idx_polint_open    ON policy_interval (agent_slug, state)
    WHERE valid_to IS NULL;
CREATE INDEX idx_polint_range   ON policy_interval (valid_from, valid_to);

-- One open interval per (domain, agent, provenance) at any time.
CREATE UNIQUE INDEX idx_polint_one_open
    ON policy_interval (domain, agent_slug, prov)
    WHERE valid_to IS NULL;


-- The '*' group, one interval per domain. Provides the fallback state
-- for every agent the file does not name explicitly.
CREATE TABLE wildcard_interval (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    domain          text          NOT NULL,
    valid_from      date          NOT NULL,
    valid_to        date,
    state           policy_state  NOT NULL,
    has_wildcard_group boolean    NOT NULL,        -- false => rule_source NONE
    content_sha256  char(64)      NOT NULL REFERENCES content_blob(sha256),
    parse_version   text          NOT NULL,
    prov            provenance    NOT NULL DEFAULT 'live',
    CONSTRAINT chk_wc_order CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE UNIQUE INDEX idx_wcint_one_open ON wildcard_interval (domain, prov)
    WHERE valid_to IS NULL;
CREATE INDEX idx_wcint_lookup ON wildcard_interval (domain, valid_from DESC);


-- Domains where the robots.txt could not be trusted. Kept so we can
-- report the exclusion rate honestly rather than silently dropping them.
CREATE TABLE excluded_observation (
    domain          text          NOT NULL,
    as_of           date          NOT NULL,
    resource        resource_kind NOT NULL,
    verdict         detect_verdict NOT NULL,
    content_sha256  char(64),
    PRIMARY KEY (domain, as_of, resource)
);


-- ---------------------------------------------------------------------
-- Events — the most quotable table in the system. Every interval
-- transition writes one. "Fourteen UK news sites blocked Meta's crawler
-- in one week" is a query against this.
-- ---------------------------------------------------------------------

CREATE TABLE policy_event (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    domain        text        NOT NULL,
    agent_slug    text        REFERENCES agent(slug),   -- NULL for file-level events
    occurred_on   date        NOT NULL,
    detected_on   date        NOT NULL,
    kind          event_kind  NOT NULL,
    prev_state    policy_state,
    new_state     policy_state,
    prev_source   rule_source,
    new_source    rule_source,
    sha256_before char(64),
    sha256_after  char(64),
    prov          provenance  NOT NULL DEFAULT 'live'
);

CREATE INDEX idx_event_feed  ON policy_event (occurred_on DESC, kind);
CREATE INDEX idx_event_agent ON policy_event (agent_slug, occurred_on DESC);
CREATE INDEX idx_event_domain ON policy_event (domain, occurred_on DESC);


-- ---------------------------------------------------------------------
-- Secondary facts. Reported honestly, never used for a headline.
-- Per Ahrefs' 137k-domain study, 97% of llms.txt files are never fetched
-- by anyone — adoption is interesting, efficacy is not claimed.
-- ---------------------------------------------------------------------

CREATE TABLE llms_txt_fact (
    domain          text     NOT NULL,
    as_of           date     NOT NULL,
    present         boolean  NOT NULL,
    byte_len        integer,
    parses_markdown boolean,
    has_h1          boolean,
    section_count   smallint,
    link_count      smallint,
    offsite_link_pct real,
    content_sha256  char(64),
    PRIMARY KEY (domain, as_of)
);

CREATE TABLE sitemap_fact (
    domain              text     NOT NULL,
    as_of               date     NOT NULL,
    present             boolean  NOT NULL,
    root_element        text,                     -- sitemapindex | urlset | invalid
    child_count         integer,                  -- TOP LEVEL ONLY, never expanded
    lastmod_min         date,
    lastmod_max         date,
    lastmod_coverage    real,                     -- fraction of entries carrying lastmod
    declared_in_robots  boolean  NOT NULL DEFAULT false,
    content_sha256      char(64),
    PRIMARY KEY (domain, as_of)
);


-- ---------------------------------------------------------------------
-- Effective policy — the resolution rule, in one place, once.
-- Everything downstream reads this, never the base tables.
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION effective_policy(as_of_date date)
RETURNS TABLE (
    domain      text,
    agent_slug  text,
    state       policy_state,
    src         rule_source
)
LANGUAGE sql STABLE AS $$
    WITH explicit AS (
        SELECT pi.domain, pi.agent_slug, pi.state
        FROM policy_interval pi
        WHERE pi.valid_from <= as_of_date
          AND (pi.valid_to IS NULL OR pi.valid_to > as_of_date)
    ),
    wildcard AS (
        SELECT wi.domain, wi.state, wi.has_wildcard_group
        FROM wildcard_interval wi
        WHERE wi.valid_from <= as_of_date
          AND (wi.valid_to IS NULL OR wi.valid_to > as_of_date)
    )
    -- The wildcard table is the domain spine: we write exactly one row per
    -- domain per successfully parsed robots.txt, including the case where
    -- the file has no '*' group. A domain absent from `wildcard` at this
    -- date has no trustworthy observation and is correctly absent here
    -- rather than silently counted as ALLOWED.
    SELECT
        w.domain,
        a.slug,
        COALESCE(e.state,
                 CASE WHEN w.has_wildcard_group THEN w.state ELSE 'ALLOWED' END
        )::policy_state,
        CASE
            WHEN e.state IS NOT NULL          THEN 'EXPLICIT'
            WHEN w.has_wildcard_group IS TRUE THEN 'WILDCARD'
            ELSE 'NONE'
        END::rule_source
    FROM wildcard w
    CROSS JOIN agent a
    LEFT JOIN explicit e ON e.domain = w.domain AND e.agent_slug = a.slug
    WHERE a.active AND a.verified;
$$;

COMMENT ON FUNCTION effective_policy IS
    'Single source of truth for resolving (domain, agent) -> state at a date.
     Filters to verified, active agents only. Do not reimplement this logic
     anywhere else — every published figure must flow through it.';


-- ---------------------------------------------------------------------
-- Rollups. One materialised view per published claim. The site reads
-- ONLY from these; a CI test greps site/ for hardcoded numbers.
-- ---------------------------------------------------------------------

CREATE MATERIALIZED VIEW mv_state_by_day_agent AS
SELECT
    d.as_of::date AS as_of,
    ep.agent_slug,
    ep.state,
    ep.src,
    count(*) AS domain_count
FROM generate_series(
        (SELECT min(valid_from)::timestamp FROM wildcard_interval),
        current_date::timestamp,
        interval '1 day'
     ) AS d(as_of)
CROSS JOIN LATERAL effective_policy(d.as_of::date) ep
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE UNIQUE INDEX ON mv_state_by_day_agent (as_of, agent_slug, state, src);

COMMENT ON MATERIALIZED VIEW mv_state_by_day_agent IS
    'Supports: "N% of the panel blocked <agent> on <date>."
     Always report the src breakdown alongside — an EXPLICIT block is a
     deliberate decision, a WILDCARD block is collateral. Conflating them
     is the mistake every competing dataset makes.';


-- The divergence view: the finding only this dataset can produce.
CREATE MATERIALIZED VIEW mv_training_vs_search AS
WITH weeks AS (
    SELECT gs::date AS as_of
    FROM generate_series(
            (SELECT min(valid_from)::timestamp FROM wildcard_interval),
            current_date::timestamp,
            interval '7 days'
         ) AS gs
),
snapshot AS (
    -- One resolved policy row per (week, domain, agent). Evaluated once.
    SELECT w.as_of, ep.domain, ep.agent_slug, ep.state
    FROM weeks w
    CROSS JOIN LATERAL effective_policy(w.as_of) ep
),
-- Every (training agent, search agent) pair belonging to the same operator.
pairs AS (
    SELECT t.slug AS train_slug, s.slug AS search_slug, t.operator
    FROM agent t
    JOIN agent s ON s.operator = t.operator AND s.purpose = 'search_index'
    WHERE t.purpose = 'training'
)
SELECT
    st.as_of,
    p.operator,
    count(*) FILTER (WHERE st.state = 'BLOCKED' AND ss.state <> 'BLOCKED')
        AS blocks_training_allows_search,
    count(*) FILTER (WHERE st.state = 'BLOCKED' AND ss.state =  'BLOCKED')
        AS blocks_both,
    count(*) FILTER (WHERE st.state <> 'BLOCKED' AND ss.state <> 'BLOCKED')
        AS allows_both,
    count(*) FILTER (WHERE st.state <> 'BLOCKED' AND ss.state =  'BLOCKED')
        AS allows_training_blocks_search   -- rare; if it is not rare, suspect a bug
FROM pairs p
JOIN snapshot st ON st.agent_slug = p.train_slug
JOIN snapshot ss ON ss.agent_slug = p.search_slug
                AND ss.domain     = st.domain
                AND ss.as_of      = st.as_of
GROUP BY 1, 2
WITH NO DATA;

CREATE UNIQUE INDEX ON mv_training_vs_search (as_of, operator);

COMMENT ON MATERIALIZED VIEW mv_training_vs_search IS
    'The headline candidate: sites that refuse to be trained on but accept
     being cited. Requires the operator/purpose taxonomy in agents.yml,
     which is an editorial claim we defend publicly. Axel owns it.';


-- Remaining rollups live in warehouse/rollups/*.sql, one file per view,
-- each with a header comment stating the exact claim it supports:
--   mv_state_by_day_agent_country
--   mv_state_by_day_agent_vertical
--   mv_state_by_operator_purpose
--   mv_events_weekly
--   mv_llmstxt_adoption
--   mv_sitemap_presence
--   mv_detect_gate_health      <- the parser-corruption canary; alerted on

COMMIT;
