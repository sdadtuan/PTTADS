-- Phase 3 T3 — Launch QA runs (Temporal LaunchQAWorkflow)
-- Apply: ./scripts/apply_pg_ddl_v3_launch_qa.sh

BEGIN;

CREATE TABLE IF NOT EXISTS launch_qa_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    external_campaign_id    VARCHAR(128) NOT NULL,
    campaign_name           VARCHAR(255),
    status                  VARCHAR(32) NOT NULL DEFAULT 'in_progress'
                            CHECK (status IN ('in_progress', 'passed', 'failed', 'blocked')),
    checklist               JSONB NOT NULL DEFAULT '{}'::jsonb,
    launch_ready            BOOLEAN NOT NULL DEFAULT FALSE,
    temporal_workflow_id    VARCHAR(128),
    temporal_run_id         VARCHAR(128),
    started_by              TEXT,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_launch_qa_client
    ON launch_qa_runs (client_id, started_at DESC);

COMMENT ON TABLE launch_qa_runs IS 'Launch QA checklist runs (Phase 3 T3 / FR-CO-04).';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-launch-qa', 'launch_qa_runs for LaunchQAWorkflow')
ON CONFLICT (version) DO NOTHING;

COMMIT;
