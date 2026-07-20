-- Email Marketing OS — EM-3 extension (journeys, journey_steps)
-- Prerequisite: email_mkt_v1 (+ EM-1 preference_tokens optional)
-- Apply: ./scripts/apply_pg_ddl_email_mkt_em3.sh

BEGIN;

CREATE TABLE IF NOT EXISTS email_mkt.journeys (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    trigger_type        VARCHAR(64) NOT NULL DEFAULT 'segment_enter',
    graph_json          JSONB NOT NULL DEFAULT '{"nodes":[],"edges":[]}'::jsonb,
    entry_segment_id    UUID REFERENCES email_mkt.segments (id),
    status              VARCHAR(32) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'active', 'paused', 'archived')),
    enrolled_count      INT NOT NULL DEFAULT 0,
    created_by          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journeys_client ON email_mkt.journeys (client_id, status);

CREATE TABLE IF NOT EXISTS email_mkt.journey_steps (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journey_id          UUID NOT NULL REFERENCES email_mkt.journeys (id) ON DELETE CASCADE,
    step_key            VARCHAR(64) NOT NULL,
    step_type           VARCHAR(32) NOT NULL
                        CHECK (step_type IN ('trigger', 'wait', 'send', 'branch', 'exit')),
    config_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (journey_id, step_key)
);

CREATE INDEX IF NOT EXISTS idx_journey_steps_journey ON email_mkt.journey_steps (journey_id, sort_order);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_send_queue_journey_step'
          AND conrelid = 'email_mkt.send_queue'::regclass
    ) THEN
        ALTER TABLE email_mkt.send_queue
            ADD CONSTRAINT fk_send_queue_journey_step
            FOREIGN KEY (journey_step_id) REFERENCES email_mkt.journey_steps (id);
    END IF;
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'skip fk_send_queue_journey_step: %', SQLERRM;
END $$;

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_em3', 'Email Marketing journeys + journey_steps (EM-3)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
