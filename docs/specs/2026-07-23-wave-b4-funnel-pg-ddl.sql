-- Wave B4 — Lead funnel + presales PG DDL (S0 cutover prep)
-- Apply AFTER v3 leads OLTP:
--   psql "$DATABASE_URL" -f docs/specs/2026-07-23-wave-b4-funnel-pg-ddl.sql
-- Or: ./scripts/apply_pg_ddl_wave_b4_funnel.sh
--
-- Nest still uses SQLite bridge until PTT_CRM_LEADS_FUNNEL_PG=1 (future flag).
-- This DDL enables dual-write / read replica sync in a later sprint.

BEGIN;

-- ---------------------------------------------------------------------------
-- crm_leads — funnel columns (mirror SQLite care + review_queue in meta_json)
-- ---------------------------------------------------------------------------

ALTER TABLE crm_leads
    ADD COLUMN IF NOT EXISTS care_stage_current TEXT NOT NULL DEFAULT 'first_contact',
    ADD COLUMN IF NOT EXISTS care_stages_done_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS first_assigned_at TIMESTAMPTZ;

COMMENT ON COLUMN crm_leads.care_stage_current IS 'Wave B4 B2 gate — current care stage key';
COMMENT ON COLUMN crm_leads.care_stages_done_json IS 'Wave B4 — map stage_key → completed_at ISO';
COMMENT ON COLUMN crm_leads.first_assigned_at IS 'First AM assignment timestamp for B2 SLA';

CREATE INDEX IF NOT EXISTS idx_crm_leads_review_queue_active
    ON crm_leads ((meta_json->'review_queue'->>'active'))
    WHERE (meta_json->'review_queue'->>'active') = 'true';

-- ---------------------------------------------------------------------------
-- crm_lead_presales — mirror SQLite crm_lead_presales
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS crm_lead_presales (
    id                      BIGSERIAL PRIMARY KEY,
    sqlite_presales_id      BIGINT UNIQUE,
    lead_id                 BIGINT NOT NULL,
    service_slug            TEXT NOT NULL DEFAULT '',
    stage                   TEXT NOT NULL DEFAULT 'lead',
    status                  TEXT NOT NULL DEFAULT 'active',
    assigned_am             BIGINT,
    lifecycle_id            BIGINT,
    stage_entered_at        TIMESTAMPTZ,
    notes                   TEXT NOT NULL DEFAULT '',
    draft_marketing_plan_id BIGINT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT crm_lead_presales_lead_unique UNIQUE (lead_id),
    CONSTRAINT crm_lead_presales_lead_fk FOREIGN KEY (lead_id)
        REFERENCES crm_leads (sqlite_lead_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_crm_lead_presales_stage ON crm_lead_presales (stage);
CREATE INDEX IF NOT EXISTS idx_crm_lead_presales_status ON crm_lead_presales (status);

-- ---------------------------------------------------------------------------
-- crm_lead_presales_tasks
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS crm_lead_presales_tasks (
    id              BIGSERIAL PRIMARY KEY,
    sqlite_task_id  BIGINT UNIQUE,
    presales_id     BIGINT NOT NULL REFERENCES crm_lead_presales (id) ON DELETE CASCADE,
    stage           TEXT NOT NULL DEFAULT '',
    step_index      INTEGER NOT NULL DEFAULT 0,
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    form_fields     JSONB NOT NULL DEFAULT '[]'::jsonb,
    form_data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    ai_output       TEXT NOT NULL DEFAULT '',
    ai_prompt_key   TEXT NOT NULL DEFAULT '',
    is_done         BOOLEAN NOT NULL DEFAULT FALSE,
    done_at         TIMESTAMPTZ,
    done_by         BIGINT,
    notes           TEXT NOT NULL DEFAULT '',
    is_custom       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crm_lead_presales_tasks_presales
    ON crm_lead_presales_tasks (presales_id, stage, step_index);

-- ---------------------------------------------------------------------------
-- Schema version marker
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ptt_schema_migrations (
    id          TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes       TEXT NOT NULL DEFAULT ''
);

INSERT INTO ptt_schema_migrations (id, notes)
VALUES ('2026-07-23-wave-b4-funnel', 'crm_leads funnel cols + crm_lead_presales tables')
ON CONFLICT (id) DO NOTHING;

COMMIT;
