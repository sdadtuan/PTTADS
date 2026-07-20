-- PTT Agency Platform — PostgreSQL DDL v3 (lead ingest rules snapshot)
-- Apply AFTER v3-leads-oltp on databases running PG-primary ingest.
--   psql $DATABASE_URL -f docs/specs/2026-07-17-postgresql-ddl-v3-leads-ingest-config.sql
--
-- Phase 2 — decouple worker ingest from SQLite OLTP reads (config, assign, catalog).
-- Populated by: ./scripts/sync_lead_ingest_config.sh

BEGIN;

CREATE TABLE IF NOT EXISTS crm_ingest_rules_snapshot (
    id                  SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    lead_config         JSONB NOT NULL DEFAULT '{}'::jsonb,
    staff_rows          JSONB NOT NULL DEFAULT '[]'::jsonb,
    assignment_state    JSONB NOT NULL DEFAULT '[]'::jsonb,
    staff_assign_scope  JSONB NOT NULL DEFAULT '[]'::jsonb,
    catalog_services    JSONB NOT NULL DEFAULT '[]'::jsonb,
    catalog_industries  JSONB NOT NULL DEFAULT '[]'::jsonb,
    staff_workload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_from         TEXT NOT NULL DEFAULT 'sqlite'
);

INSERT INTO crm_ingest_rules_snapshot (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE crm_ingest_rules_snapshot IS
    'Snapshot of SQLite lead rules (facebook config, assign, catalog) for PG-primary ingest worker.';

INSERT INTO schema_migrations (version, description)
VALUES (
    '2026-07-17-v3-ingest',
    'crm_ingest_rules_snapshot for PG-primary ingest (no SQLite OLTP reads)'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
