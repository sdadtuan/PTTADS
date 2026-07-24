-- PTT Meta Enterprise — PostgreSQL DDL v4 (B8 measurement parity)
-- Apply AFTER v3 performance + hub map:
--   ./scripts/apply_pg_ddl_v4_meta_enterprise.sh

BEGIN;

CREATE TABLE IF NOT EXISTS meta_alerts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel                 VARCHAR(16) NOT NULL DEFAULT 'meta',
    external_campaign_id    VARCHAR(128),
    alert_type              VARCHAR(64) NOT NULL,
    severity                VARCHAR(16) NOT NULL DEFAULT 'warning',
    metric_value            NUMERIC(18, 6),
    threshold_value         NUMERIC(18, 6),
    message                 TEXT NOT NULL DEFAULT '',
    performance_date        DATE,
    dedupe_key              VARCHAR(255) NOT NULL,
    notified_at             TIMESTAMPTZ,
    acknowledged_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT meta_alerts_dedupe UNIQUE (dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_meta_alerts_client_created
    ON meta_alerts (client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_meta_alerts_open
    ON meta_alerts (client_id, alert_type)
    WHERE acknowledged_at IS NULL;

COMMENT ON TABLE meta_alerts IS 'Meta measurement alerts (B8) — deduped by dedupe_key';

INSERT INTO schema_migrations (version, description)
VALUES ('2026-07-24-v4-meta-enterprise', 'meta_alerts B8 measurement parity')
ON CONFLICT (version) DO NOTHING;

COMMIT;
