ALTER TABLE domain_language ADD COLUMN IF NOT EXISTS category text;

COMMENT ON COLUMN domain_language.category IS
    'Best-effort site type from homepage HTML or domain: news, ecommerce, gov, edu, tech, other.';
