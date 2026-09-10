-- mv_events_weekly
-- Claim: "K domains of vertical V changed policy for <agent> in week W."
-- Source table: policy_event. Never use this for a stock 'percent blocked' headline.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_events_weekly AS
SELECT
    date_trunc('week', occurred_on)::date AS week_start,
    kind,
    agent_slug,
    count(*) AS event_count
FROM policy_event
GROUP BY 1, 2, 3
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS mv_events_weekly_uq
    ON mv_events_weekly (week_start, kind, agent_slug);
