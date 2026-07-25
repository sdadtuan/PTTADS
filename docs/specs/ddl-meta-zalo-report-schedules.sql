-- Meta + Zalo scheduled client reports (PROD-P0-RPT / Prod-S2)
-- Apply after core DDL and daily_performance tables

CREATE TABLE IF NOT EXISTS meta_report_schedules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    report_scope            VARCHAR(16) NOT NULL DEFAULT 'clients'
                            CHECK (report_scope IN ('clients', 'campaigns')),
    export_format           VARCHAR(8) NOT NULL DEFAULT 'pdf'
                            CHECK (export_format IN ('csv', 'pdf')),
    window_days             INT NOT NULL DEFAULT 7,
    cadence                 VARCHAR(16) NOT NULL DEFAULT 'weekly'
                            CHECK (cadence IN ('weekly', 'monthly')),
    day_of_week             INT NOT NULL DEFAULT 0,
    day_of_month            INT NOT NULL DEFAULT 1,
    recipient_emails_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
    cc_emails_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
    bcc_emails_json         JSONB NOT NULL DEFAULT '[]'::jsonb,
    portal_link_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at             DATE,
    last_sent_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_report_schedules_due
    ON meta_report_schedules (next_run_at)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_meta_report_schedules_client
    ON meta_report_schedules (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS meta_report_schedule_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id     UUID NOT NULL REFERENCES meta_report_schedules (id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'sent', 'skipped', 'failed')),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_meta_report_runs_schedule
    ON meta_report_schedule_runs (schedule_id, created_at DESC);

CREATE TABLE IF NOT EXISTS zalo_report_schedules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    report_scope            VARCHAR(16) NOT NULL DEFAULT 'clients'
                            CHECK (report_scope IN ('clients', 'campaigns')),
    export_format           VARCHAR(8) NOT NULL DEFAULT 'pdf'
                            CHECK (export_format IN ('csv', 'pdf')),
    window_days             INT NOT NULL DEFAULT 7,
    cadence                 VARCHAR(16) NOT NULL DEFAULT 'weekly'
                            CHECK (cadence IN ('weekly', 'monthly')),
    day_of_week             INT NOT NULL DEFAULT 0,
    day_of_month            INT NOT NULL DEFAULT 1,
    recipient_emails_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
    cc_emails_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
    bcc_emails_json         JSONB NOT NULL DEFAULT '[]'::jsonb,
    portal_link_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at             DATE,
    last_sent_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zalo_report_schedules_due
    ON zalo_report_schedules (next_run_at)
    WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_zalo_report_schedules_client
    ON zalo_report_schedules (client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS zalo_report_schedule_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id     UUID NOT NULL REFERENCES zalo_report_schedules (id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'sent', 'skipped', 'failed')),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_zalo_report_runs_schedule
    ON zalo_report_schedule_runs (schedule_id, created_at DESC);
