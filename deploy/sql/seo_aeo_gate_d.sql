-- Gate D — CWV snapshots + crawl import tracking (Enterprise & BI)
CREATE TABLE IF NOT EXISTS seo_aeo.seo_cwv_snapshots (
    id                SERIAL PRIMARY KEY,
    customer_id       INTEGER NOT NULL,
    url               TEXT NOT NULL DEFAULT '',
    lcp_ms            REAL,
    cls               REAL,
    inp_ms            REAL,
    performance_score REAL,
    cwv_rating        TEXT NOT NULL DEFAULT 'unknown',
    source            TEXT NOT NULL DEFAULT 'pagespeed',
    checked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_cwv_customer ON seo_aeo.seo_cwv_snapshots (customer_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_crawl_import_log (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    rows_imported   INTEGER NOT NULL DEFAULT 0,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_crawl_log_customer ON seo_aeo.seo_crawl_import_log (customer_id, imported_at DESC);
