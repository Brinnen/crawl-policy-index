-- Language is an observed homepage declaration, not country.
-- html lang / Content-Language / og:locale. Unknown is valid.
-- Homepage is fetched once per domain, and never when robots.txt disallows /.

ALTER TYPE resource_kind ADD VALUE IF NOT EXISTS 'html_home';
ALTER TYPE fetch_outcome ADD VALUE IF NOT EXISTS 'skipped_robots';

CREATE TABLE IF NOT EXISTS domain_language (
    domain            text PRIMARY KEY,
    language          text,
    language_source   text        NOT NULL,
    observed_at       timestamptz NOT NULL,
    content_sha256    text,
    http_status       integer,
    panel_version     text,
    robots_allowed    boolean     NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_domain_language_lang
    ON domain_language (language);

COMMENT ON COLUMN domain_language.language IS
    'ISO 639-1/2 primary subtag from the homepage. Not a country code.';
COMMENT ON COLUMN domain_language.language_source IS
    'html_lang | content_language | og_locale | missing | robots_disallow | http_error';
