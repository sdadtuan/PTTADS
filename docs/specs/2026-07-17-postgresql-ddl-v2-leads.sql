-- PTT Agency Platform — PostgreSQL DDL v2 (crm_leads read replica)
-- Apply AFTER v1 on existing databases:
--   psql $DATABASE_URL -f docs/specs/2026-07-17-postgresql-ddl-v2-leads.sql
-- Or: ./scripts/apply_pg_ddl_v2_leads.sh
--
-- Phase 1b Bước 5: read replica only — SQLite remains OLTP primary.
-- Sync worker (Bước 6) populates this table from ptt.db.
-- No FK to clients.id (cross-DB bridge via agency_client_id only).

BEGIN;

-- ---------------------------------------------------------------------------
-- CRM leads read replica (from SQLite crm_leads)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS crm_leads (
    sqlite_lead_id      BIGINT PRIMARY KEY,
    full_name           TEXT NOT NULL DEFAULT '',
    phone               TEXT NOT NULL DEFAULT '',
    email               TEXT NOT NULL DEFAULT '',
    status              VARCHAR(64) NOT NULL DEFAULT '',
    source              VARCHAR(64) NOT NULL DEFAULT '',
    owner_id            BIGINT,
    is_duplicate        BOOLEAN NOT NULL DEFAULT FALSE,
    meta_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Denormalized from meta_json — maintained by sync worker (Bước 6)
    agency_client_id    UUID,
    channel             VARCHAR(64) NOT NULL DEFAULT '',
    external_lead_id    VARCHAR(128),
    campaign_id         VARCHAR(128),
    received_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ,
    -- Sync metadata
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_version        BIGINT NOT NULL DEFAULT 1,
    CONSTRAINT crm_leads_sqlite_id_positive CHECK (sqlite_lead_id > 0)
);

COMMENT ON TABLE crm_leads IS
    'Read replica of SQLite crm_leads. LeadV1.id = sqlite_lead_id. No FK to clients (Phase 1b).';
COMMENT ON COLUMN crm_leads.sqlite_lead_id IS 'Stable id — maps to SQLite crm_leads.id and LeadV1.id';
COMMENT ON COLUMN crm_leads.agency_client_id IS 'From meta_json.agency_client_id — logical link to clients.id';
COMMENT ON COLUMN crm_leads.synced_at IS 'Last successful upsert from SQLite sync worker';

CREATE INDEX IF NOT EXISTS idx_crm_leads_agency_client
    ON crm_leads (agency_client_id)
    WHERE agency_client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_crm_leads_created_at
    ON crm_leads (created_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_crm_leads_external_lead_id
    ON crm_leads (external_lead_id)
    WHERE external_lead_id IS NOT NULL AND external_lead_id <> '';

CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads (status);
CREATE INDEX IF NOT EXISTS idx_crm_leads_channel ON crm_leads (channel);

CREATE INDEX IF NOT EXISTS idx_crm_leads_not_duplicate
    ON crm_leads (sqlite_lead_id DESC)
    WHERE is_duplicate IS NOT TRUE;

-- ---------------------------------------------------------------------------
-- Sync watermark (Bước 6)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS crm_leads_sync_state (
    id              SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sqlite_id  BIGINT NOT NULL DEFAULT 0,
    last_sync_at    TIMESTAMPTZ,
    last_full_at    TIMESTAMPTZ,
    rows_total      BIGINT NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO crm_leads_sync_state (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE crm_leads_sync_state IS 'Singleton watermark for SQLite → PG lead sync';

-- ---------------------------------------------------------------------------
-- Schema version marker
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     VARCHAR(32) PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v2-leads', 'crm_leads read replica + sync_state')
ON CONFLICT (version) DO NOTHING;

COMMIT;
