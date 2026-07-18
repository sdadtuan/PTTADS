-- PTT Agency Platform — PostgreSQL DDL v3 (daily_performance + metrics)
-- Apply AFTER v3-leads-oltp:
--   psql $DATABASE_URL -f docs/specs/2026-07-17-postgresql-ddl-v3-performance.sql
-- Or: ./scripts/apply_pg_ddl_v3.sh
--
-- Phase 2 Track M: Meta closed-loop storage + derived metrics snapshots.

BEGIN;

-- ---------------------------------------------------------------------------
-- Daily ad performance (Meta Marketing API insights)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS daily_performance (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel                 VARCHAR(16) NOT NULL DEFAULT 'meta'
                            CHECK (channel IN ('meta', 'zalo', 'google')),
    external_account_id     VARCHAR(128),
    external_campaign_id    VARCHAR(128) NOT NULL,
    external_campaign_name  VARCHAR(255),
    hub_campaign_map_id     UUID REFERENCES hub_campaign_map (id) ON DELETE SET NULL,
    performance_date        DATE NOT NULL,
    currency                VARCHAR(3) NOT NULL DEFAULT 'VND',
    spend                   NUMERIC(18, 2) NOT NULL DEFAULT 0,
    impressions             BIGINT NOT NULL DEFAULT 0,
    clicks                  BIGINT NOT NULL DEFAULT 0,
    reach                   BIGINT,
    frequency               NUMERIC(10, 4),
    cpc                     NUMERIC(18, 4),
    cpm                     NUMERIC(18, 4),
    ctr                     NUMERIC(10, 6),
    leads_platform          INT NOT NULL DEFAULT 0,
    leads_crm               INT NOT NULL DEFAULT 0,
    conversions             NUMERIC(18, 4) NOT NULL DEFAULT 0,
    conversion_value        NUMERIC(18, 2) NOT NULL DEFAULT 0,
    raw_insights            JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_version            BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT daily_performance_unique
        UNIQUE (client_id, channel, external_campaign_id, performance_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_performance_client_date
    ON daily_performance (client_id, performance_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_performance_campaign_date
    ON daily_performance (external_campaign_id, performance_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_performance_hub_map
    ON daily_performance (hub_campaign_map_id)
    WHERE hub_campaign_map_id IS NOT NULL;

COMMENT ON TABLE daily_performance IS
    'Daily ad metrics from Meta insights API. leads_crm from PG crm_leads count by campaign/day.';
COMMENT ON COLUMN daily_performance.leads_platform IS 'Meta-reported lead actions (if available)';
COMMENT ON COLUMN daily_performance.leads_crm IS 'CRM lead count matched via utm/campaign map';

-- ---------------------------------------------------------------------------
-- Derived metrics snapshots (CPL, ROAS — computed by metrics engine)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    kpi_code            VARCHAR(64) NOT NULL REFERENCES kpi_definitions (code),
    channel             VARCHAR(16) NOT NULL DEFAULT 'meta',
    external_campaign_id VARCHAR(128),
    hub_campaign_map_id UUID REFERENCES hub_campaign_map (id) ON DELETE SET NULL,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    granularity         VARCHAR(16) NOT NULL DEFAULT 'day'
                        CHECK (granularity IN ('day', 'week', 'month')),
    value_numeric       NUMERIC(18, 6) NOT NULL,
    value_json          JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_snapshots_unique
    ON metrics_snapshots (
        client_id,
        kpi_code,
        channel,
        COALESCE(external_campaign_id, ''),
        period_start,
        period_end,
        granularity
    );

CREATE INDEX IF NOT EXISTS idx_metrics_snapshots_client_kpi
    ON metrics_snapshots (client_id, kpi_code, period_end DESC);

COMMENT ON TABLE metrics_snapshots IS
    'Cached KPI values (CPL, ROAS, …) from metrics engine cron';

-- ---------------------------------------------------------------------------
-- CAPI event log (Track M — dedup + observability)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS capi_event_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    event_name          VARCHAR(64) NOT NULL,
    event_id            VARCHAR(128) NOT NULL,
    lead_id             BIGINT,
    pixel_id            VARCHAR(64),
    payload_hash        VARCHAR(64) NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed', 'skipped')),
    meta_response       JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at             TIMESTAMPTZ,
    CONSTRAINT capi_event_log_dedup UNIQUE (client_id, event_id, event_name)
);

CREATE INDEX IF NOT EXISTS idx_capi_event_log_lead
    ON capi_event_log (lead_id, created_at DESC)
    WHERE lead_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_capi_event_log_status
    ON capi_event_log (status, created_at)
    WHERE status IN ('pending', 'failed');

COMMENT ON TABLE capi_event_log IS
    'Server-side Meta CAPI dispatch log — Phase 2 pilot';

-- ---------------------------------------------------------------------------
-- Schema version
-- ---------------------------------------------------------------------------

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-performance', 'daily_performance, metrics_snapshots, capi_event_log')
ON CONFLICT (version) DO NOTHING;

COMMIT;
