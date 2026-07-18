-- Phase 3 P4 — client creative approval inbox (portal)
-- Apply: ./scripts/apply_pg_ddl_v3_creatives.sh

BEGIN;

CREATE TABLE IF NOT EXISTS creative_submissions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    title                   VARCHAR(255) NOT NULL,
    description             TEXT,
    external_campaign_id    VARCHAR(128),
    external_campaign_name  VARCHAR(255),
    version                 INT NOT NULL DEFAULT 1 CHECK (version > 0),
    asset_url               TEXT,
    asset_type              VARCHAR(32) NOT NULL DEFAULT 'image',
    status                  VARCHAR(32) NOT NULL DEFAULT 'pending_client'
                            CHECK (status IN ('pending_client', 'approved', 'rejected', 'withdrawn')),
    submitted_by            TEXT,
    submitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by             TEXT,
    reviewed_at             TIMESTAMPTZ,
    review_note             TEXT,
    temporal_workflow_id    VARCHAR(128),
    temporal_run_id         VARCHAR(128),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_creative_submissions_client_pending
    ON creative_submissions (client_id, submitted_at DESC)
    WHERE status = 'pending_client';

CREATE INDEX IF NOT EXISTS idx_creative_submissions_client_status
    ON creative_submissions (client_id, status, submitted_at DESC);

COMMENT ON TABLE creative_submissions IS
    'Client-facing creative approval queue (Phase 3 P4). AM uploads; client approver on portal.';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-creatives', 'creative_submissions portal approval inbox')
ON CONFLICT (version) DO NOTHING;

COMMIT;
