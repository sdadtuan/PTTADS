-- PTT Meta Enterprise — PostgreSQL DDL v6 (B10 adset/ad insight granularity)
-- Apply AFTER v3 performance + v4 meta enterprise:
--   ./scripts/apply_pg_ddl_v6_meta_insights_level.sh

BEGIN;

ALTER TABLE daily_performance
    ADD COLUMN IF NOT EXISTS insight_level VARCHAR(16) NOT NULL DEFAULT 'campaign';

ALTER TABLE daily_performance
    ADD COLUMN IF NOT EXISTS external_adset_id VARCHAR(128) NOT NULL DEFAULT '';

ALTER TABLE daily_performance
    ADD COLUMN IF NOT EXISTS external_adset_name VARCHAR(255);

UPDATE daily_performance
SET insight_level = 'campaign',
    external_adset_id = COALESCE(external_adset_id, '')
WHERE insight_level IS NULL OR insight_level = '' OR external_adset_id IS NULL;

ALTER TABLE daily_performance DROP CONSTRAINT IF EXISTS daily_performance_unique;

DROP INDEX IF EXISTS idx_daily_performance_grain_unique;

CREATE UNIQUE INDEX idx_daily_performance_grain_unique
    ON daily_performance (
        client_id,
        channel,
        external_campaign_id,
        external_adset_id,
        insight_level,
        performance_date
    );

CREATE INDEX IF NOT EXISTS idx_daily_performance_adset_date
    ON daily_performance (client_id, external_adset_id, performance_date DESC)
    WHERE insight_level = 'adset' AND external_adset_id <> '';

COMMENT ON COLUMN daily_performance.insight_level IS 'Granularity: campaign (default), adset, ad — B10/B11';
COMMENT ON COLUMN daily_performance.external_adset_id IS 'Meta ad set id; empty string for campaign-level rows';

INSERT INTO schema_migrations (version, description)
VALUES ('2026-07-24-v6-meta-insights-level', 'daily_performance insight_level + adset columns B10')
ON CONFLICT (version) DO NOTHING;

COMMIT;
