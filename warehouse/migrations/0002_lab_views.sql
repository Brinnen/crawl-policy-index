-- Lab-only views. Agents in registry/agents.yml are unverified.
-- Do not publish these figures. effective_policy() stays empty until verified=true.

BEGIN;

CREATE OR REPLACE VIEW v_lab_gptbot_named AS
SELECT
    pi.domain,
    pi.state,
    pi.valid_from,
    pi.valid_to,
    pi.parse_version,
    pi.content_sha256
FROM policy_interval pi
WHERE pi.agent_slug = 'openai-gptbot'
  AND pi.valid_to IS NULL;

COMMENT ON VIEW v_lab_gptbot_named IS
    'LAB ONLY. Open explicit GPTBot intervals. Not a published figure.';

CREATE OR REPLACE VIEW v_lab_gptbot_named_grouped AS
SELECT
    CASE
        WHEN domain = 'amazon.com' OR domain LIKE 'amazon.%' THEN 'amazon.com'
        ELSE domain
    END AS group_key,
    count(*) AS domain_rows,
    count(*) FILTER (WHERE state = 'BLOCKED') AS named_block_rows,
    count(*) FILTER (WHERE state = 'ALLOWED') AS named_allow_rows,
    count(*) FILTER (WHERE state = 'PARTIAL') AS named_partial_rows
FROM v_lab_gptbot_named
GROUP BY 1;

COMMENT ON VIEW v_lab_gptbot_named_grouped IS
    'LAB ONLY. Collapses amazon.* ccTLDs to amazon.com. Not a published figure.';

CREATE OR REPLACE VIEW v_lab_named AS
SELECT
    pi.domain,
    pi.state,
    pi.valid_from,
    pi.valid_to,
    pi.parse_version,
    a.slug AS agent_slug,
    a.ua_token,
    a.display_name,
    a.operator,
    a.purpose
FROM policy_interval pi
JOIN agent a ON a.slug = pi.agent_slug
WHERE pi.valid_to IS NULL;

COMMENT ON VIEW v_lab_named IS
    'LAB ONLY. Open explicit intervals for every registered agent. Not a published figure.';

CREATE OR REPLACE VIEW v_lab_gptbot_blanket AS
SELECT
    wi.domain,
    wi.state,
    wi.valid_from,
    wi.valid_to,
    wi.content_sha256
FROM wildcard_interval wi
WHERE wi.valid_to IS NULL
  AND wi.has_wildcard_group
  AND wi.state = 'BLOCKED'
  AND NOT EXISTS (
      SELECT 1
      FROM policy_interval pi
      WHERE pi.domain = wi.domain
        AND pi.agent_slug = 'openai-gptbot'
        AND pi.valid_to IS NULL
  );

COMMENT ON VIEW v_lab_gptbot_blanket IS
    'LAB ONLY. Open * BLOCKED intervals on domains that did not name GPTBot. Not a published figure.';

COMMIT;
