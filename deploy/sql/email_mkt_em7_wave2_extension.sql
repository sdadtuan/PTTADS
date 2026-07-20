-- Email Marketing EM-7 / Wave 2 — analytics, reports, daily metrics
-- Prerequisite: email_mkt_v1 (+ em1/em3 extensions)
-- Apply: ./scripts/apply_pg_ddl_email_mkt_em7.sh

BEGIN;

CREATE TABLE IF NOT EXISTS email_mkt.daily_metrics (
    client_id       UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    metric_date     DATE NOT NULL,
    metric_name     VARCHAR(64) NOT NULL,
    metric_value    NUMERIC(18, 4) NOT NULL DEFAULT 0,
    dimensions      JSONB NOT NULL DEFAULT '{}'::jsonb,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (client_id, metric_date, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_name
    ON email_mkt.daily_metrics (metric_name, metric_date DESC);

CREATE TABLE IF NOT EXISTS email_mkt.report_schedules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id               UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    report_type             VARCHAR(32) NOT NULL DEFAULT 'executive'
                            CHECK (report_type IN ('executive', 'campaign', 'deliverability')),
    cadence                 VARCHAR(16) NOT NULL DEFAULT 'weekly'
                            CHECK (cadence IN ('weekly', 'monthly')),
    day_of_week             INT NOT NULL DEFAULT 0,
    day_of_month            INT NOT NULL DEFAULT 1,
    recipient_emails_json   JSONB NOT NULL DEFAULT '[]'::jsonb,
    cc_emails_json          JSONB NOT NULL DEFAULT '[]'::jsonb,
    bcc_emails_json         JSONB NOT NULL DEFAULT '[]'::jsonb,
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at             DATE,
    last_sent_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_schedules_due
    ON email_mkt.report_schedules (next_run_at)
    WHERE active = TRUE;

CREATE TABLE IF NOT EXISTS email_mkt.report_schedule_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id     UUID NOT NULL REFERENCES email_mkt.report_schedules (id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'sent', 'skipped', 'failed')),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_report_runs_schedule
    ON email_mkt.report_schedule_runs (schedule_id, created_at DESC);

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_em7', 'Email Marketing Wave 2 — daily_metrics, report schedules')
ON CONFLICT (version) DO NOTHING;

COMMIT;
