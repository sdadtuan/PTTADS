-- Email Marketing OS — EM-11 journey execution (enrollments)
-- Prerequisite: email_mkt_em3
-- Apply: ./scripts/apply_pg_ddl_email_mkt_em11.sh

BEGIN;

CREATE TABLE IF NOT EXISTS email_mkt.journey_enrollments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journey_id          UUID NOT NULL REFERENCES email_mkt.journeys (id) ON DELETE CASCADE,
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id) ON DELETE CASCADE,
    current_step_key    VARCHAR(64),
    status              VARCHAR(32) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'exited', 'failed')),
    enrolled_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_run_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (journey_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_journey_enrollments_due
    ON email_mkt.journey_enrollments (status, next_run_at)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_journey_enrollments_journey
    ON email_mkt.journey_enrollments (journey_id, status);

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_em11', 'Email Marketing journey enrollments + execution (EM-11)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
