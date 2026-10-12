-- Country the homepage stated (schema address / contact), never from html lang.
ALTER TABLE domain_language ADD COLUMN IF NOT EXISTS country text;

COMMENT ON COLUMN domain_language.country IS
    'ISO 3166-1 alpha-2 when the homepage stated an address country. Empty is valid.';
