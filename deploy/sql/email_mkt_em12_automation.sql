-- Email Marketing OS — EM-12 enterprise automation (experiments + journey events)
-- Prerequisite: email_mkt_em11
-- Apply: ./scripts/apply_pg_ddl_email_mkt_em12.sh

BEGIN;

CREATE TABLE IF NOT EXISTS email_mkt.experiments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    campaign_id         UUID REFERENCES email_mkt.campaigns (id) ON DELETE SET NULL,
    name                VARCHAR(255) NOT NULL,
    experiment_type     VARCHAR(32) NOT NULL DEFAULT 'subject'
                        CHECK (experiment_type IN ('subject', 'content', 'send_time')),
    hypothesis          TEXT,
    status              VARCHAR(32) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'running', 'completed', 'cancelled')),
    winner_variant_key  VARCHAR(32),
    config_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiments_client ON email_mkt.experiments (client_id, status);
CREATE INDEX IF NOT EXISTS idx_experiments_campaign ON email_mkt.experiments (campaign_id);

CREATE TABLE IF NOT EXISTS email_mkt.experiment_variants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id       UUID NOT NULL REFERENCES email_mkt.experiments (id) ON DELETE CASCADE,
    variant_key         VARCHAR(32) NOT NULL,
    label               VARCHAR(128) NOT NULL,
    config_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    split_pct           INT NOT NULL DEFAULT 50,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, variant_key)
);

CREATE TABLE IF NOT EXISTS email_mkt.experiment_observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id       UUID NOT NULL REFERENCES email_mkt.experiments (id) ON DELETE CASCADE,
    variant_key         VARCHAR(32) NOT NULL,
    metric_name         VARCHAR(64) NOT NULL,
    metric_value        NUMERIC NOT NULL DEFAULT 0,
    sample_size         INT NOT NULL DEFAULT 0,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source              VARCHAR(32) NOT NULL DEFAULT 'rollup',
    UNIQUE (experiment_id, variant_key, metric_name, observed_at)
);

CREATE TABLE IF NOT EXISTS email_mkt.experiment_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id       UUID NOT NULL REFERENCES email_mkt.experiments (id) ON DELETE CASCADE,
    decision            VARCHAR(32) NOT NULL,
    rationale           TEXT,
    decided_by          TEXT,
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_mkt.journey_trigger_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id) ON DELETE CASCADE,
    event_type          VARCHAR(32) NOT NULL,
    source_send_id      UUID REFERENCES email_mkt.send_queue (id),
    source_campaign_id  UUID REFERENCES email_mkt.campaigns (id),
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journey_trigger_events_pending
    ON email_mkt.journey_trigger_events (processed_at, occurred_at)
    WHERE processed_at IS NULL;

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_em12', 'Email Marketing experiments + journey trigger events (EM-12)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
