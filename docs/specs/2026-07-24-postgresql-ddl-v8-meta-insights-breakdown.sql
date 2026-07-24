-- Meta Enterprise B8.1 — daily_performance_breakdown (publisher_platform, etc.)
-- Apply after v4 meta enterprise + daily_performance:
--   ./scripts/apply_pg_ddl_v8_meta_insights_breakdown.sh

CREATE TABLE IF NOT EXISTS daily_performance_breakdown (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel             VARCHAR(16) NOT NULL DEFAULT 'meta',
    external_campaign_id VARCHAR(128) NOT NULL,
    performance_date    DATE NOT NULL,
    breakdown_type      VARCHAR(32) NOT NULL,
    breakdown_value     VARCHAR(64) NOT NULL,
    spend               NUMERIC(18, 2) NOT NULL DEFAULT 0,
    impressions         BIGINT NOT NULL DEFAULT 0,
    clicks              BIGINT NOT NULL DEFAULT 0,
    leads_platform      INT NOT NULL DEFAULT 0,
    raw_insights        JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT daily_performance_breakdown_unique
        UNIQUE (client_id, channel, external_campaign_id, performance_date, breakdown_type, breakdown_value)
);

CREATE INDEX IF NOT EXISTS idx_daily_perf_breakdown_client_date
    ON daily_performance_breakdown (client_id, performance_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_perf_breakdown_campaign_type
    ON daily_performance_breakdown (external_campaign_id, breakdown_type, performance_date DESC);

INSERT INTO schema_migrations (version, applied_at)
VALUES ('2026-07-24-v8-meta-insights-breakdown', NOW())
ON CONFLICT (version) DO NOTHING;
