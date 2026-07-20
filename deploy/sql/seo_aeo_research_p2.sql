-- P2 Research depth — SERP snapshots, keyword clusters (PG seo_aeo)

CREATE TABLE IF NOT EXISTS seo_aeo.seo_keyword_clusters (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    name            TEXT NOT NULL DEFAULT '',
    intent          TEXT NOT NULL DEFAULT 'informational',
    notes           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_seo_clusters_customer ON seo_aeo.seo_keyword_clusters (customer_id, status);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_serp_snapshots (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    keyword_id      INTEGER,
    phrase          TEXT NOT NULL DEFAULT '',
    snapshot_date   TEXT NOT NULL DEFAULT '',
    results_json    TEXT NOT NULL DEFAULT '[]',
    source          TEXT NOT NULL DEFAULT 'stub',
    created_at      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_seo_serp_customer_date ON seo_aeo.seo_serp_snapshots (customer_id, snapshot_date DESC);
