-- mv_detect_gate_health
-- Claim: none. This is the parser-corruption canary.
-- Alert when any verdict share moves more than 3 percentage points day over day.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_detect_gate_health AS
SELECT
    first_seen_on AS as_of,
    detect_result,
    count(*) AS blob_count
FROM content_blob
WHERE resource = 'robots_txt'
GROUP BY 1, 2
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS mv_detect_gate_health_uq
    ON mv_detect_gate_health (as_of, detect_result);
