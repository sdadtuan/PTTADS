-- PTT Agency Platform — PostgreSQL DDL v3 (crm_leads OLTP primary)
-- Apply AFTER v2 on existing databases:
--   ./scripts/apply_pg_ddl_v3.sh
--   psql $DATABASE_URL -f docs/specs/2026-07-17-postgresql-ddl-v3-leads-oltp.sql
--
-- Phase 2 Track W: promote crm_leads from read replica → OLTP primary.
-- SQLite ptt.db becomes shadow/fallback for legacy modules (not dropped).
-- Requires: v1 (clients) + v2 (crm_leads) already applied.
--
-- Pre-flight (staging):
--   1. Reconcile SQLite ↔ PG: ./scripts/reconcile_lead_replica.sh
--   2. Fix orphan agency_client_id rows before VALIDATE FK:
--        UPDATE crm_leads SET agency_client_id = NULL
--        WHERE agency_client_id IS NOT NULL
--          AND agency_client_id NOT IN (SELECT id FROM clients);
--   3. psql -c "ALTER TABLE crm_leads VALIDATE CONSTRAINT crm_leads_agency_client_fk;"

BEGIN;

-- ---------------------------------------------------------------------------
-- crm_leads — OLTP columns (additive migration from v2 replica)
-- ---------------------------------------------------------------------------

ALTER TABLE crm_leads
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR(120),
    ADD COLUMN IF NOT EXISTS write_source VARCHAR(32) NOT NULL DEFAULT 'sync';

COMMENT ON COLUMN crm_leads.write_source IS
    'Origin of last write: sync | nest | flask_shadow | staging';
COMMENT ON COLUMN crm_leads.updated_at IS 'Last business write (Nest OLTP Phase 2)';
COMMENT ON COLUMN crm_leads.updated_by IS 'Actor id/name from X-PTT-Actor or assigned_by';

-- Backfill updated_at from synced_at for existing replica rows
UPDATE crm_leads
SET updated_at = COALESCE(updated_at, synced_at, created_at, NOW())
WHERE updated_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_crm_leads_updated_at
    ON crm_leads (updated_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_crm_leads_owner
    ON crm_leads (owner_id)
    WHERE owner_id IS NOT NULL;

-- FK to clients (NOT VALID — validate after orphan cleanup)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'crm_leads_agency_client_fk'
    ) THEN
        ALTER TABLE crm_leads
            ADD CONSTRAINT crm_leads_agency_client_fk
            FOREIGN KEY (agency_client_id) REFERENCES clients (id)
            ON DELETE SET NULL
            NOT VALID;
    END IF;
END $$;

COMMENT ON TABLE crm_leads IS
    'Phase 2 OLTP primary for LeadV1. sqlite_lead_id remains stable id (LeadV1.id). '
    'Was read replica in Phase 1b; Nest write authoritative after cutover.';

-- ---------------------------------------------------------------------------
-- Assignment audit (PG-native; mirrors SQLite crm_lead_assignment_logs)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS crm_lead_assignment_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sqlite_lead_id  BIGINT NOT NULL,
    from_owner_id   BIGINT,
    to_owner_id     BIGINT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    assigned_by     VARCHAR(120) NOT NULL DEFAULT '',
    correlation_id  VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_assignment_log_lead
    ON crm_lead_assignment_log (sqlite_lead_id, created_at DESC);

COMMENT ON TABLE crm_lead_assignment_log IS
    'PG assignment audit — populated by Nest PATCH assign (Phase 2).';

-- ---------------------------------------------------------------------------
-- Sync state — bidirectional (SQLite→PG ingest + PG→SQLite shadow)
-- ---------------------------------------------------------------------------

ALTER TABLE crm_leads_sync_state
    ADD COLUMN IF NOT EXISTS sync_mode VARCHAR(16) NOT NULL DEFAULT 'sqlite_to_pg';

ALTER TABLE crm_leads_sync_state
    ADD COLUMN IF NOT EXISTS last_shadow_at TIMESTAMPTZ;

COMMENT ON COLUMN crm_leads_sync_state.sync_mode IS
    'sqlite_to_pg | pg_primary | paused';

CREATE TABLE IF NOT EXISTS crm_leads_shadow_state (
    id              SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_pg_version BIGINT NOT NULL DEFAULT 0,
    last_sqlite_id  BIGINT NOT NULL DEFAULT 0,
    last_shadow_at  TIMESTAMPTZ,
    rows_shadowed   BIGINT NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO crm_leads_shadow_state (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE crm_leads_shadow_state IS
    'Watermark PG → SQLite shadow sync (Phase 2 rollback safety)';

-- ---------------------------------------------------------------------------
-- Meta token vault extensions (Track M — client_channel_accounts)
-- ---------------------------------------------------------------------------

ALTER TABLE client_channel_accounts
    ADD COLUMN IF NOT EXISTS access_token_encrypted BYTEA,
    ADD COLUMN IF NOT EXISTS token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS token_scopes TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_token_refresh_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS token_status VARCHAR(32) NOT NULL DEFAULT 'unknown'
        CHECK (token_status IN ('unknown', 'valid', 'expiring', 'expired', 'revoked'));

COMMENT ON COLUMN client_channel_accounts.access_token_encrypted IS
    'AES-GCM encrypted long-lived token; key from env PTT_TOKEN_VAULT_KEY';
COMMENT ON COLUMN client_channel_accounts.credential_ref IS
    'Legacy ref — prefer access_token_encrypted Phase 2';

CREATE INDEX IF NOT EXISTS idx_channel_accounts_token_expiry
    ON client_channel_accounts (token_expires_at)
    WHERE token_expires_at IS NOT NULL AND status = 'active';

-- ---------------------------------------------------------------------------
-- Hub ↔ Meta campaign map cache (bridge SQLite Hub → PG analytics)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hub_campaign_map (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    hub_campaign_id         BIGINT NOT NULL,
    channel                 VARCHAR(16) NOT NULL DEFAULT 'meta'
                            CHECK (channel IN ('meta', 'zalo', 'google')),
    external_campaign_id    VARCHAR(128) NOT NULL,
    external_campaign_name  VARCHAR(255),
    external_account_id     VARCHAR(128),
    target_cpl_vnd          NUMERIC(18, 2),
    meta                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    mapped_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, channel, external_campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_hub_campaign_map_client
    ON hub_campaign_map (client_id, active);

CREATE INDEX IF NOT EXISTS idx_hub_campaign_map_external
    ON hub_campaign_map (external_campaign_id)
    WHERE active IS TRUE;

COMMENT ON TABLE hub_campaign_map IS
    'Denormalized Hub campaign ↔ Meta campaign ID. hub_campaign_id = SQLite crm_hub row (no cross-DB FK).';
COMMENT ON COLUMN hub_campaign_map.target_cpl_vnd IS
    'Manual AM target for closed-loop dashboard delta (Phase 2)';

-- ---------------------------------------------------------------------------
-- Meta insights sync watermark (Track M)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta_insights_sync_state (
    id                  SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sync_at        TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_error          TEXT,
    accounts_total      INT NOT NULL DEFAULT 0,
    accounts_failed     INT NOT NULL DEFAULT 0,
    rows_upserted       BIGINT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO meta_insights_sync_state (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Schema version
-- ---------------------------------------------------------------------------

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-leads-oltp', 'crm_leads OLTP columns, assignment log, shadow sync, token vault, hub_campaign_map')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Post-apply (manual after orphan cleanup):
-- ALTER TABLE crm_leads VALIDATE CONSTRAINT crm_leads_agency_client_fk;
