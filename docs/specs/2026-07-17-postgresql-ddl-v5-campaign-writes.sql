-- Phase 4 F1 — Meta campaign write requests (approval queue)
BEGIN;

CREATE TABLE IF NOT EXISTS campaign_write_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel                 VARCHAR(16) NOT NULL DEFAULT 'meta'
                            CHECK (channel IN ('meta', 'google')),
    external_account_id     VARCHAR(128),
    external_campaign_id    VARCHAR(128) NOT NULL,
    external_campaign_name  VARCHAR(255),
    change_type             VARCHAR(32) NOT NULL DEFAULT 'daily_budget'
                            CHECK (change_type IN ('daily_budget', 'status', 'name')),
    old_value               JSONB NOT NULL DEFAULT '{}'::jsonb,
    new_value               JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                  VARCHAR(32) NOT NULL DEFAULT 'pending_approval'
                            CHECK (status IN (
                                'pending_approval', 'approved', 'rejected',
                                'executed', 'execution_failed', 'withdrawn'
                            )),
    submitted_by            TEXT NOT NULL,
    approved_by             TEXT,
    approved_at             TIMESTAMPTZ,
    executed_at             TIMESTAMPTZ,
    execution_error         TEXT,
    review_note             TEXT,
    temporal_workflow_id    VARCHAR(128),
    temporal_run_id         VARCHAR(128),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaign_write_pending
    ON campaign_write_requests (client_id, created_at DESC)
    WHERE status = 'pending_approval';

CREATE INDEX IF NOT EXISTS idx_campaign_write_campaign
    ON campaign_write_requests (external_campaign_id, created_at DESC);

COMMENT ON TABLE campaign_write_requests IS
    'Phase 4 U-P3-01 — approved Meta/Google campaign mutations';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v5-campaign-writes', 'campaign_write_requests approval queue')
ON CONFLICT (version) DO NOTHING;

COMMIT;
