-- Wave Z3 — creative channel tag for Zalo workflow
-- Apply: ./scripts/apply_pg_ddl_zalo_z3.sh

BEGIN;

ALTER TABLE creative_submissions
    ADD COLUMN IF NOT EXISTS channel VARCHAR(16) NOT NULL DEFAULT 'meta';

CREATE INDEX IF NOT EXISTS idx_creative_submissions_channel_status
    ON creative_submissions (channel, status, submitted_at DESC);

COMMENT ON COLUMN creative_submissions.channel IS 'Ads channel tag: meta | google | zalo (Z3-1)';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-25-zalo-z3-creatives-channel', 'creative_submissions.channel for Zalo creative workflow')
ON CONFLICT (version) DO NOTHING;

COMMIT;
