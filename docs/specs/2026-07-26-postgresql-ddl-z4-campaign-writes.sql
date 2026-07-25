-- Prod-Z4 — extend campaign_write_requests for channel=zalo (GAP-Z4-01)
BEGIN;

ALTER TABLE campaign_write_requests
    DROP CONSTRAINT IF EXISTS campaign_write_requests_channel_check;

ALTER TABLE campaign_write_requests
    ADD CONSTRAINT campaign_write_requests_channel_check
    CHECK (channel IN ('meta', 'google', 'zalo'));

ALTER TABLE campaign_write_requests
    DROP CONSTRAINT IF EXISTS campaign_write_requests_change_type_check;

ALTER TABLE campaign_write_requests
    ADD CONSTRAINT campaign_write_requests_change_type_check
    CHECK (change_type IN (
        'daily_budget', 'status', 'name',
        'create_campaign', 'create_adset', 'create_ad',
        'update_ad_creative', 'update_ad_copy'
    ));

COMMENT ON TABLE campaign_write_requests IS
    'Phase 4 / Prod-Z4 — Meta/Google/Zalo campaign mutations with approval queue';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-26-z4-campaign-writes', 'campaign_write_requests channel=zalo + extended change_type')
ON CONFLICT (version) DO NOTHING;

COMMIT;
