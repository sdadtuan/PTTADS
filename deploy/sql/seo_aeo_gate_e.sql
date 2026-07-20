-- Gate E — Enterprise depth (OKR, crawl connector, GA4 revenue)
-- PostgreSQL / seo_aeo schema

CREATE TABLE IF NOT EXISTS seo_aeo.seo_strategy_goals (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    period          TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_strategy_goals_customer ON seo_aeo.seo_strategy_goals (customer_id, status);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_strategy_kpis (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    goal_id         INTEGER NOT NULL REFERENCES seo_aeo.seo_strategy_goals(id) ON DELETE CASCADE,
    initiative_id   INTEGER,
    metric_key      TEXT NOT NULL DEFAULT '',
    metric_label    TEXT NOT NULL DEFAULT '',
    target_value    REAL,
    current_value   REAL,
    unit            TEXT NOT NULL DEFAULT '',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_strategy_kpis_goal ON seo_aeo.seo_strategy_kpis (goal_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_crawl_schedules (
    customer_id     INTEGER PRIMARY KEY,
    frequency_days  INTEGER NOT NULL DEFAULT 30,
    webhook_secret  TEXT NOT NULL DEFAULT '',
    last_ingest_at  TIMESTAMPTZ,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE seo_aeo.seo_initiatives ADD COLUMN IF NOT EXISTS goal_id INTEGER;

ALTER TABLE seo_aeo.seo_ga4_daily_stats ADD COLUMN IF NOT EXISTS conversions REAL NOT NULL DEFAULT 0;
ALTER TABLE seo_aeo.seo_ga4_daily_stats ADD COLUMN IF NOT EXISTS revenue REAL NOT NULL DEFAULT 0;
