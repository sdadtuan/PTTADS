-- Email Marketing OS — PostgreSQL schema v1 (EM-0)
-- Prerequisite: clients + client_channel_accounts (postgresql-ddl-v1)
-- Apply: ./scripts/apply_pg_ddl_email_mkt.sh

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS email_mkt;

CREATE TABLE IF NOT EXISTS email_mkt.workspaces (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    default_from_name   VARCHAR(128),
    default_from_email  VARCHAR(255),
    default_reply_to    VARCHAR(255),
    esp_provider        VARCHAR(32) NOT NULL DEFAULT 'sendgrid',
    esp_account_ref     UUID REFERENCES client_channel_accounts (id),
    daily_send_cap      INT NOT NULL DEFAULT 10000,
    frequency_cap_7d    INT NOT NULL DEFAULT 5,
    timezone            VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id)
);

CREATE TABLE IF NOT EXISTS email_mkt.contacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    email               VARCHAR(320) NOT NULL,
    email_normalized    VARCHAR(320) NOT NULL,
    first_name          VARCHAR(128),
    last_name           VARCHAR(128),
    crm_customer_id     TEXT,
    crm_lead_id         TEXT,
    lifecycle_stage     VARCHAR(32) DEFAULT 'subscriber',
    locale              VARCHAR(16) DEFAULT 'vi-VN',
    timezone            VARCHAR(64),
    attributes          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, email_normalized)
);

CREATE INDEX IF NOT EXISTS idx_contacts_client ON email_mkt.contacts (client_id);
CREATE INDEX IF NOT EXISTS idx_contacts_crm ON email_mkt.contacts (client_id, crm_customer_id);

CREATE TABLE IF NOT EXISTS email_mkt.consent_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id) ON DELETE CASCADE,
    topic               VARCHAR(64) NOT NULL DEFAULT 'marketing',
    status              VARCHAR(32) NOT NULL
                        CHECK (status IN ('opted_in', 'opted_out', 'pending_confirm')),
    source              VARCHAR(64) NOT NULL,
    source_url          TEXT,
    ip_address          INET,
    user_agent          TEXT,
    consent_version     VARCHAR(32),
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by         TEXT
);

CREATE INDEX IF NOT EXISTS idx_consent_contact ON email_mkt.consent_records (contact_id, topic, recorded_at DESC);

CREATE TABLE IF NOT EXISTS email_mkt.suppression_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID REFERENCES clients (id) ON DELETE CASCADE,
    email_normalized    VARCHAR(320) NOT NULL,
    reason              VARCHAR(32) NOT NULL
                        CHECK (reason IN (
                            'unsubscribe', 'complaint', 'hard_bounce',
                            'manual', 'legal_hold', 'global_block'
                        )),
    scope               VARCHAR(16) NOT NULL DEFAULT 'client'
                        CHECK (scope IN ('client', 'global', 'brand')),
    source_send_id      UUID,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by          TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_suppression_unique
    ON email_mkt.suppression_entries (COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid), email_normalized, reason)
    WHERE expires_at IS NULL;

CREATE TABLE IF NOT EXISTS email_mkt.segments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    segment_type        VARCHAR(32) NOT NULL DEFAULT 'dynamic'
                        CHECK (segment_type IN ('static', 'dynamic', 'lifecycle', 'rfm')),
    definition_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    member_count        INT NOT NULL DEFAULT 0,
    last_computed_at    TIMESTAMPTZ,
    refresh_cron        VARCHAR(64),
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_mkt.segment_members (
    segment_id          UUID NOT NULL REFERENCES email_mkt.segments (id) ON DELETE CASCADE,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id) ON DELETE CASCADE,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (segment_id, contact_id)
);

CREATE TABLE IF NOT EXISTS email_mkt.templates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    subject_template    TEXT NOT NULL,
    html_body           TEXT NOT NULL,
    text_body           TEXT,
    blocks_json         JSONB NOT NULL DEFAULT '[]'::jsonb,
    locale              VARCHAR(16) DEFAULT 'vi-VN',
    version             INT NOT NULL DEFAULT 1,
    status              VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_mkt.campaigns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    workspace_id        UUID NOT NULL REFERENCES email_mkt.workspaces (id),
    name                VARCHAR(255) NOT NULL,
    campaign_type       VARCHAR(32) NOT NULL DEFAULT 'broadcast',
    segment_id          UUID REFERENCES email_mkt.segments (id),
    template_id         UUID NOT NULL REFERENCES email_mkt.templates (id),
    status              VARCHAR(32) NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'pending_approval', 'approved', 'scheduled',
                            'sending', 'sent', 'paused', 'cancelled', 'failed'
                        )),
    scheduled_at        TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    audience_count      INT,
    approval_id         UUID,
    experiment_config   JSONB NOT NULL DEFAULT '{}'::jsonb,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_mkt.send_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    campaign_id         UUID REFERENCES email_mkt.campaigns (id),
    journey_step_id     UUID,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id),
    status              VARCHAR(32) NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending', 'processing', 'sent', 'delivered',
                            'bounced', 'failed', 'skipped', 'cancelled'
                        )),
    skip_reason         VARCHAR(64),
    scheduled_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at             TIMESTAMPTZ,
    esp_message_id      VARCHAR(255),
    esp_provider        VARCHAR(32),
    subject_rendered    TEXT,
    personalization     JSONB NOT NULL DEFAULT '{}'::jsonb,
    tracking_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    attempts            INT NOT NULL DEFAULT 0,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_send_queue_pending
    ON email_mkt.send_queue (status, scheduled_at)
    WHERE status IN ('pending', 'processing');

CREATE INDEX IF NOT EXISTS idx_send_queue_campaign ON email_mkt.send_queue (campaign_id);

CREATE TABLE IF NOT EXISTS email_mkt.engagement_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL,
    send_id             UUID REFERENCES email_mkt.send_queue (id),
    contact_id          UUID REFERENCES email_mkt.contacts (id),
    event_type          VARCHAR(32) NOT NULL
                        CHECK (event_type IN (
                            'delivered', 'open', 'click', 'reply',
                            'unsubscribe', 'complaint', 'bounce_soft', 'bounce_hard'
                        )),
    occurred_at         TIMESTAMPTZ NOT NULL,
    url                 TEXT,
    user_agent          TEXT,
    ip_address          INET,
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engagement_send ON email_mkt.engagement_events (send_id, event_type);
CREATE INDEX IF NOT EXISTS idx_engagement_client ON email_mkt.engagement_events (client_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS email_mkt.domains (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    domain              VARCHAR(255) NOT NULL,
    spf_status          VARCHAR(16) DEFAULT 'unknown',
    dkim_status         VARCHAR(16) DEFAULT 'unknown',
    dmarc_status        VARCHAR(16) DEFAULT 'unknown',
    last_checked_at     TIMESTAMPTZ,
    warm_up_stage       INT NOT NULL DEFAULT 0,
    daily_volume_cap    INT,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, domain)
);

CREATE TABLE IF NOT EXISTS email_mkt.rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope               VARCHAR(16) NOT NULL CHECK (scope IN ('global', 'brand', 'market', 'client')),
    client_id           UUID REFERENCES clients (id) ON DELETE CASCADE,
    rule_type           VARCHAR(64) NOT NULL,
    config_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority            INT NOT NULL DEFAULT 100,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rules_scope ON email_mkt.rules (scope, rule_type);

CREATE TABLE IF NOT EXISTS email_mkt.audit_log (
    id                  BIGSERIAL PRIMARY KEY,
    client_id           UUID,
    actor               TEXT NOT NULL,
    action              VARCHAR(64) NOT NULL,
    entity_type         VARCHAR(64) NOT NULL,
    entity_id           UUID,
    before_json         JSONB,
    after_json          JSONB,
    ip_address          INET,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_client ON email_mkt.audit_log (client_id, created_at DESC);

-- EM-0 seed: global governance rules (read-only defaults)
INSERT INTO email_mkt.rules (scope, rule_type, config_json, priority, enabled)
SELECT 'global', 'frequency_cap_7d', '{"max_sends": 5}'::jsonb, 10, TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM email_mkt.rules WHERE scope = 'global' AND rule_type = 'frequency_cap_7d'
);

INSERT INTO email_mkt.rules (scope, rule_type, config_json, priority, enabled)
SELECT 'global', 'quiet_hours', '{"start": "22:00", "end": "07:00", "timezone": "Asia/Ho_Chi_Minh"}'::jsonb, 20, TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM email_mkt.rules WHERE scope = 'global' AND rule_type = 'quiet_hours'
);

INSERT INTO email_mkt.rules (scope, rule_type, config_json, priority, enabled)
SELECT 'global', 'complaint_rate_threshold', '{"warn_pct": 0.1, "pause_pct": 0.3}'::jsonb, 30, TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM email_mkt.rules WHERE scope = 'global' AND rule_type = 'complaint_rate_threshold'
);

INSERT INTO email_mkt.rules (scope, rule_type, config_json, priority, enabled)
SELECT 'global', 'approval_threshold_audience', '{"min_audience": 5000, "requires_approval": true}'::jsonb, 40, TRUE
WHERE NOT EXISTS (
    SELECT 1 FROM email_mkt.rules WHERE scope = 'global' AND rule_type = 'approval_threshold_audience'
);

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_v1', 'Email Marketing OS schema email_mkt.* (EM-0)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
