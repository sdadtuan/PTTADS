-- PTT Agency Platform — PostgreSQL DDL v4 (Hub campaigns + SOP — Phase 3 Track D)
BEGIN;

-- Hub campaign metadata (mirrors SQLite crm_campaigns)
CREATE TABLE IF NOT EXISTS hub_campaigns (
    id                  BIGSERIAL PRIMARY KEY,
    sqlite_campaign_id  BIGINT UNIQUE,
    code                VARCHAR(64) NOT NULL DEFAULT '',
    name                VARCHAR(255) NOT NULL,
    channel             VARCHAR(16) NOT NULL DEFAULT 'other',
    external_ref        VARCHAR(128) NOT NULL DEFAULT '',
    utm_campaign        VARCHAR(128) NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hub_campaigns_active ON hub_campaigns (active, name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hub_campaigns_code_nn
    ON hub_campaigns (lower(trim(code)))
    WHERE trim(code) <> '';

COMMENT ON TABLE hub_campaigns IS 'PG primary for Hub campaign metadata (Phase 3 D1). sqlite_campaign_id = legacy crm_campaigns.id';

-- SOP templates (mirrors crm_sop_templates)
CREATE TABLE IF NOT EXISTS sop_templates (
    id                  BIGSERIAL PRIMARY KEY,
    sqlite_template_id  BIGINT UNIQUE,
    code                VARCHAR(64) NOT NULL DEFAULT '',
    name                VARCHAR(255) NOT NULL,
    channel             VARCHAR(16) NOT NULL DEFAULT 'other',
    description         TEXT NOT NULL DEFAULT '',
    notes               TEXT NOT NULL DEFAULT '',
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sop_templates_active ON sop_templates (active, channel);

CREATE TABLE IF NOT EXISTS sop_steps (
    id                  BIGSERIAL PRIMARY KEY,
    sqlite_step_id      BIGINT UNIQUE,
    template_id         BIGINT NOT NULL REFERENCES sop_templates (id) ON DELETE CASCADE,
    position            INT NOT NULL DEFAULT 0,
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    offset_days         INT NOT NULL DEFAULT 0,
    duration_days       INT NOT NULL DEFAULT 1,
    role                VARCHAR(32) NOT NULL DEFAULT 'any',
    required            BOOLEAN NOT NULL DEFAULT TRUE,
    checklist_json      JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sop_steps_template ON sop_steps (template_id, position);

CREATE TABLE IF NOT EXISTS sop_runs (
    id                  BIGSERIAL PRIMARY KEY,
    sqlite_run_id       BIGINT UNIQUE,
    hub_campaign_id     BIGINT REFERENCES hub_campaigns (id) ON DELETE SET NULL,
    template_id         BIGINT REFERENCES sop_templates (id) ON DELETE SET NULL,
    name                VARCHAR(255) NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    start_date          DATE,
    notes               TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sop_runs_status ON sop_runs (status, start_date);

CREATE TABLE IF NOT EXISTS sop_run_tasks (
    id                  BIGSERIAL PRIMARY KEY,
    sqlite_task_id      BIGINT UNIQUE,
    run_id              BIGINT NOT NULL REFERENCES sop_runs (id) ON DELETE CASCADE,
    step_id             BIGINT REFERENCES sop_steps (id) ON DELETE SET NULL,
    position            INT NOT NULL DEFAULT 0,
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    status              VARCHAR(32) NOT NULL DEFAULT 'pending',
    due_date            DATE,
    completed_at        TIMESTAMPTZ,
    assignee            VARCHAR(128) NOT NULL DEFAULT '',
    checklist_json      JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes               TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sop_run_tasks_run ON sop_run_tasks (run_id, position);

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v4-hub-sop', 'hub_campaigns, sop_templates, sop_steps, sop_runs, sop_run_tasks')
ON CONFLICT (version) DO NOTHING;

COMMIT;
