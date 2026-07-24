-- PTT Meta Enterprise — PostgreSQL DDL v5 (B9 conversion rules)
-- Apply AFTER v4 meta enterprise (meta_alerts):
--   ./scripts/apply_pg_ddl_v5_meta_conversion.sh

BEGIN;

CREATE TABLE IF NOT EXISTS meta_conversion_rules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID REFERENCES clients (id) ON DELETE CASCADE,
    lead_status             VARCHAR(64) NOT NULL,
    event_name              VARCHAR(64) NOT NULL,
    enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    require_meta_attribution BOOLEAN NOT NULL DEFAULT TRUE,
    value_vnd               BIGINT NOT NULL DEFAULT 0,
    notes                   TEXT NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Global (client_id NULL) + per-client rules — spec §7.2 COALESCE uniqueness via index
CREATE UNIQUE INDEX IF NOT EXISTS idx_meta_conversion_rules_uniq
    ON meta_conversion_rules (
        COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid),
        lead_status,
        event_name
    );

CREATE INDEX IF NOT EXISTS idx_meta_conversion_rules_client
    ON meta_conversion_rules (client_id, enabled)
    WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_meta_conversion_rules_global
    ON meta_conversion_rules (lead_status, event_name)
    WHERE client_id IS NULL;

COMMENT ON TABLE meta_conversion_rules IS
    'CRM lead_status → Meta CAPI event_name rules (B9 Conversion OS). NULL client_id = agency default.';
COMMENT ON COLUMN meta_conversion_rules.require_meta_attribution IS
    'When true, skip dispatch if lead lacks utm/campaign/hub attribution';
COMMENT ON COLUMN meta_conversion_rules.value_vnd IS
    'Purchase/custom value hint (VND) for value-based optimization events';

-- Default agency rules (idempotent)
INSERT INTO meta_conversion_rules (client_id, lead_status, event_name, enabled, notes)
SELECT NULL, 'qualified', 'CompleteRegistration', TRUE, 'default agency rule'
WHERE NOT EXISTS (
    SELECT 1 FROM meta_conversion_rules
    WHERE client_id IS NULL AND lead_status = 'qualified' AND event_name = 'CompleteRegistration'
);

INSERT INTO meta_conversion_rules (client_id, lead_status, event_name, enabled, notes)
SELECT NULL, 'post_sale', 'Purchase', TRUE, 'value from deal meta'
WHERE NOT EXISTS (
    SELECT 1 FROM meta_conversion_rules
    WHERE client_id IS NULL AND lead_status = 'post_sale' AND event_name = 'Purchase'
);

INSERT INTO meta_conversion_rules (client_id, lead_status, event_name, enabled, notes)
SELECT NULL, 'new', 'Lead', FALSE, 'webhook-only'
WHERE NOT EXISTS (
    SELECT 1 FROM meta_conversion_rules
    WHERE client_id IS NULL AND lead_status = 'new' AND event_name = 'Lead'
);

INSERT INTO schema_migrations (version, description)
VALUES ('2026-07-24-v5-meta-conversion', 'meta_conversion_rules B9 conversion OS')
ON CONFLICT (version) DO NOTHING;

COMMIT;
