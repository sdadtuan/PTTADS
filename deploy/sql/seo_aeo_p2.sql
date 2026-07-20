-- P2: technical issue → CRM task link + scheduled reports (PG seo_aeo schema)

ALTER TABLE seo_aeo.seo_technical_issues
    ADD COLUMN IF NOT EXISTS crm_task_id INTEGER;

ALTER TABLE seo_aeo.seo_technical_issues
    ADD COLUMN IF NOT EXISTS lifecycle_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_seo_issues_crm_task
    ON seo_aeo.seo_technical_issues (crm_task_id)
    WHERE crm_task_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS seo_aeo.seo_report_schedules (
    id                      SERIAL PRIMARY KEY,
    customer_id             INTEGER NOT NULL,
    dashboard_type          TEXT NOT NULL DEFAULT 'executive',
    cadence                 TEXT NOT NULL DEFAULT 'weekly',
    day_of_week             INTEGER NOT NULL DEFAULT 0,
    day_of_month            INTEGER NOT NULL DEFAULT 1,
    recipient_emails_json   TEXT NOT NULL DEFAULT '[]',
    active                  INTEGER NOT NULL DEFAULT 1,
    last_sent_at            TEXT,
    next_run_at             TEXT,
    created_at              TEXT NOT NULL DEFAULT '',
    updated_at              TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_seo_report_schedules_due
    ON seo_aeo.seo_report_schedules (active, next_run_at);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_report_schedule_runs (
    id              SERIAL PRIMARY KEY,
    schedule_id     INTEGER NOT NULL REFERENCES seo_aeo.seo_report_schedules(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending',
    error_message   TEXT NOT NULL DEFAULT '',
    sent_at         TEXT,
    created_at      TEXT NOT NULL DEFAULT ''
);
