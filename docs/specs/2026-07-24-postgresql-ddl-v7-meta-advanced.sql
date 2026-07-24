-- Meta Enterprise B11 — multi-pixel + intelligence snapshots
-- Apply after v4 meta enterprise (client_channel_accounts):
--   ./scripts/apply_pg_ddl_v7_meta_advanced.sh

CREATE TABLE IF NOT EXISTS meta_pixels (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_channel_account_id UUID NOT NULL REFERENCES client_channel_accounts (id) ON DELETE CASCADE,
    pixel_id                VARCHAR(64) NOT NULL,
    label                   VARCHAR(128) NOT NULL DEFAULT '',
    is_primary              BOOLEAN NOT NULL DEFAULT FALSE,
    capi_enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT meta_pixels_uniq UNIQUE (client_channel_account_id, pixel_id)
);

CREATE INDEX IF NOT EXISTS idx_meta_pixels_account_primary
    ON meta_pixels (client_channel_account_id)
    WHERE is_primary IS TRUE;

CREATE TABLE IF NOT EXISTS meta_intelligence_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID REFERENCES clients (id) ON DELETE SET NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    artifact_path   TEXT NOT NULL,
    byte_size       BIGINT NOT NULL DEFAULT 0,
    gzip            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_intel_snapshots_client_created
    ON meta_intelligence_snapshots (client_id, created_at DESC);

INSERT INTO schema_migrations (version, applied_at)
VALUES ('2026-07-24-v7-meta-advanced', NOW())
ON CONFLICT (version) DO NOTHING;
