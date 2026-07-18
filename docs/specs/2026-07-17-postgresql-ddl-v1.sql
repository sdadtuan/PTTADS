-- PTT Agency Platform — PostgreSQL DDL v1
-- Apply: psql $DATABASE_URL -f docs/specs/2026-07-17-postgresql-ddl-v1.sql
-- Docker Compose mounts this file to /docker-entrypoint-initdb.d/

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Tenant / Client
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(32) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    industry_slug   VARCHAR(64),
    status          VARCHAR(32) NOT NULL DEFAULT 'prospect'
                    CHECK (status IN (
                        'prospect', 'onboarding', 'active', 'paused',
                        'renewing', 'offboarding', 'archived'
                    )),
    owner_am_id     TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clients_status ON clients (status);
CREATE INDEX IF NOT EXISTS idx_clients_owner ON clients (owner_am_id);

CREATE TABLE IF NOT EXISTS client_onboarding_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    item_key        VARCHAR(64) NOT NULL,
    label           VARCHAR(255) NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    completed       BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at    TIMESTAMPTZ,
    completed_by    TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_onboarding_client ON client_onboarding_items (client_id);

CREATE TABLE IF NOT EXISTS client_channel_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel             VARCHAR(16) NOT NULL CHECK (channel IN ('meta', 'zalo', 'google', 'email')),
    external_account_id VARCHAR(128) NOT NULL,
    display_name        VARCHAR(255),
    credential_ref      VARCHAR(255),
    status              VARCHAR(32) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive', 'revoked', 'error')),
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, channel, external_account_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_accounts_client ON client_channel_accounts (client_id);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_channel ON client_channel_accounts (channel);

-- ---------------------------------------------------------------------------
-- Job queue
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS job_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type            VARCHAR(64) NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'failed', 'dead')),
    idempotency_key     VARCHAR(128) NOT NULL UNIQUE,
    correlation_id      VARCHAR(64),
    client_id           UUID REFERENCES clients (id) ON DELETE SET NULL,
    attempts            INT NOT NULL DEFAULT 0,
    max_attempts        INT NOT NULL DEFAULT 5,
    last_error          TEXT,
    scheduled_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_queue_status_scheduled
    ON job_queue (status, scheduled_at)
    WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_job_queue_correlation ON job_queue (correlation_id);
CREATE INDEX IF NOT EXISTS idx_job_queue_type ON job_queue (job_type);

-- ---------------------------------------------------------------------------
-- Domain events (outbox)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS domain_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(64) NOT NULL,
    aggregate_type  VARCHAR(64) NOT NULL,
    aggregate_id    TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id  VARCHAR(64),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_domain_events_unpublished
    ON domain_events (created_at)
    WHERE published_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_domain_events_type ON domain_events (event_type);

-- ---------------------------------------------------------------------------
-- Notifications
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS notification_inbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id    TEXT NOT NULL,
    category        VARCHAR(32) NOT NULL DEFAULT 'system',
    title           VARCHAR(255) NOT NULL,
    body            TEXT,
    link_url        TEXT,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_recipient
    ON notification_inbox (recipient_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_unread
    ON notification_inbox (recipient_id)
    WHERE read_at IS NULL;

-- ---------------------------------------------------------------------------
-- KPI definitions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kpi_definitions (
    code            VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    formula         TEXT NOT NULL,
    source_tables   JSONB NOT NULL DEFAULT '[]'::jsonb,
    granularity     VARCHAR(32) NOT NULL DEFAULT 'day',
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed KPI dictionary
INSERT INTO kpi_definitions (code, name, formula, source_tables, granularity, description) VALUES
    ('SPEND', 'Chi phí quảng cáo', 'SUM(daily_performance.spend)', '["daily_performance"]', 'day', 'Tổng chi phí ads'),
    ('IMPRESSIONS', 'Lượt hiển thị', 'SUM(daily_performance.impressions)', '["daily_performance"]', 'day', NULL),
    ('CLICKS', 'Lượt click', 'SUM(daily_performance.clicks)', '["daily_performance"]', 'day', NULL),
    ('CTR', 'Tỷ lệ click', 'clicks / NULLIF(impressions, 0)', '["daily_performance"]', 'day', NULL),
    ('CPC', 'Chi phí/click', 'spend / NULLIF(clicks, 0)', '["daily_performance"]', 'day', NULL),
    ('CPM', 'CPM', 'spend / NULLIF(impressions, 0) * 1000', '["daily_performance"]', 'day', NULL),
    ('LEADS', 'Số lead', 'COUNT(lead events)', '["crm_leads","tracking_events"]', 'day', NULL),
    ('CPL', 'Chi phí/lead', 'spend / NULLIF(leads, 0)', '["daily_performance","crm_leads"]', 'week', 'Closed-loop Phase 2'),
    ('CPA', 'Chi phí/chuyển đổi', 'spend / NULLIF(conversions, 0)', '["daily_performance"]', 'day', NULL),
    ('ROAS', 'ROAS', 'conversion_value / NULLIF(spend, 0)', '["daily_performance","tracking_events"]', 'week', NULL),
    ('WIN_RATE', 'Tỷ lệ chốt', 'won / NULLIF(qualified, 0)', '["crm_leads"]', 'month', 'CRM KPI'),
    ('SLA_BREACH', 'Vi phạm SLA', 'COUNT(overdue SLA objects)', '["crm_leads","crm_cases"]', 'day', NULL)
ON CONFLICT (code) DO NOTHING;

-- Default onboarding checklist template function
CREATE OR REPLACE FUNCTION seed_client_onboarding(p_client_id UUID)
RETURNS VOID AS $$
BEGIN
    INSERT INTO client_onboarding_items (client_id, item_key, label, sort_order) VALUES
        (p_client_id, 'contract_signed', 'Hợp đồng ký', 1),
        (p_client_id, 'billing_setup', 'Billing / phương thức thanh toán', 2),
        (p_client_id, 'bm_access', 'Business Manager access', 3),
        (p_client_id, 'ad_account_access', 'Ad account access', 4),
        (p_client_id, 'page_access', 'Facebook Page access', 5),
        (p_client_id, 'pixel_dataset', 'Pixel / dataset', 6),
        (p_client_id, 'client_approver', 'Client approver contact', 7),
        (p_client_id, 'naming_convention', 'Naming convention agreed', 8),
        (p_client_id, 'utm_template', 'UTM template', 9),
        (p_client_id, 'sla_confirmed', 'SLA hours confirmed', 10),
        (p_client_id, 'hub_contract', 'Hub contract created', 11),
        (p_client_id, 'webhook_test', 'Webhook test lead OK', 12)
    ON CONFLICT (client_id, item_key) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

COMMIT;
