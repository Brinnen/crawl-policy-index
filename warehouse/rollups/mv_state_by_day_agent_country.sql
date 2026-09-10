-- mv_state_by_day_agent_country
-- Claim: "N% of panel domains in country CC blocked <agent> on <date>."
-- Assumes: panel_version currently loaded; parse_version of effective_policy rows.
-- Site may read this view only after REFRESH MATERIALIZED VIEW.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_state_by_day_agent_country AS
SELECT
    d.as_of::date AS as_of,
    ep.agent_slug,
    ep.state,
    ep.src,
    pd.country,
    count(*) AS domain_count
FROM generate_series(
        (SELECT COALESCE(min(valid_from), current_date)::timestamp FROM wildcard_interval),
        current_date::timestamp,
        interval '1 day'
     ) AS d(as_of)
CROSS JOIN LATERAL effective_policy(d.as_of::date) ep
JOIN panel_domain pd ON pd.domain = ep.domain
GROUP BY 1, 2, 3, 4, 5
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS mv_state_by_day_agent_country_uq
    ON mv_state_by_day_agent_country (as_of, agent_slug, state, src, country);
