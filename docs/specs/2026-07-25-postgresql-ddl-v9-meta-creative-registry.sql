-- Meta Enterprise B12 — ad_id ↔ creative asset registry
-- Apply after v3 creatives + v4 meta enterprise:
--   ./scripts/apply_pg_ddl_v9_meta_creative_registry.sh

BEGIN;

CREATE TABLE IF NOT EXISTS meta_ad_creative_links (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    creative_submission_id  UUID NOT NULL REFERENCES creative_submissions (id) ON DELETE RESTRICT,
    external_ad_id          VARCHAR(64) NOT NULL,
    external_adset_id       VARCHAR(64),
    external_campaign_id    VARCHAR(128),
    external_creative_id    VARCHAR(64),
    link_source             VARCHAR(32) NOT NULL DEFAULT 'manual'
                            CHECK (link_source IN ('manual', 'campaign_write', 'graph_sync')),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    linked_by               TEXT,
    note                    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_meta_ad_creative_links_active_ad
    ON meta_ad_creative_links (client_id, external_ad_id)
    WHERE is_active IS TRUE;

CREATE INDEX IF NOT EXISTS idx_meta_ad_creative_links_creative
    ON meta_ad_creative_links (creative_submission_id, is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_meta_ad_creative_links_campaign
    ON meta_ad_creative_links (client_id, external_campaign_id, is_active)
    WHERE is_active IS TRUE;

COMMENT ON TABLE meta_ad_creative_links IS
    'B12 registry: maps Meta Graph external_ad_id to approved creative_submissions asset.';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-25-v9-meta-creative-registry', 'meta_ad_creative_links B12 creative registry')
ON CONFLICT (version) DO NOTHING;

COMMIT;
