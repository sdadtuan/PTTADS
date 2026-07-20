-- SEO/AEO Enterprise backlog (Phase 3 enterprise / 5D BI)
-- Applied via ptt_seo/pg_schema.py → ensure_enterprise_pg_schema()

CREATE TABLE IF NOT EXISTS seo_aeo.seo_entities (
    id                SERIAL PRIMARY KEY,
    customer_id       INTEGER NOT NULL,
    entity_name       TEXT NOT NULL DEFAULT '',
    entity_type       TEXT NOT NULL DEFAULT 'category',
    same_as_json      JSONB NOT NULL DEFAULT '[]',
    confidence_score  REAL,
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_entities_customer ON seo_aeo.seo_entities (customer_id, entity_type);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_entity_links (
    id                SERIAL PRIMARY KEY,
    customer_id       INTEGER NOT NULL,
    source_entity_id  INTEGER NOT NULL,
    target_entity_id  INTEGER NOT NULL,
    link_type         TEXT NOT NULL DEFAULT 'related',
    weight            REAL NOT NULL DEFAULT 1.0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, source_entity_id, target_entity_id, link_type)
);
CREATE INDEX IF NOT EXISTS idx_seo_entity_links_customer ON seo_aeo.seo_entity_links (customer_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_pages (
    id                  SERIAL PRIMARY KEY,
    customer_id         INTEGER NOT NULL,
    url                 TEXT NOT NULL DEFAULT '',
    title               TEXT NOT NULL DEFAULT '',
    slug                TEXT NOT NULL DEFAULT '',
    content_type        TEXT NOT NULL DEFAULT '',
    schema_type         TEXT NOT NULL DEFAULT '',
    primary_keyword_id  INTEGER,
    primary_entity_id   INTEGER,
    status              TEXT NOT NULL DEFAULT 'unknown',
    last_crawled_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, url)
);
CREATE INDEX IF NOT EXISTS idx_seo_pages_customer ON seo_aeo.seo_pages (customer_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_rank_tracked_keywords (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    keyword_id      INTEGER,
    phrase          TEXT NOT NULL DEFAULT '',
    target_url      TEXT NOT NULL DEFAULT '',
    locale          TEXT NOT NULL DEFAULT 'vi-VN',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, phrase, locale)
);
CREATE INDEX IF NOT EXISTS idx_seo_rank_kw_customer ON seo_aeo.seo_rank_tracked_keywords (customer_id, status);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_rank_snapshots (
    id                  SERIAL PRIMARY KEY,
    tracked_keyword_id  INTEGER NOT NULL,
    snapshot_date       DATE NOT NULL,
    position            REAL,
    url_found           TEXT NOT NULL DEFAULT '',
    source              TEXT NOT NULL DEFAULT 'manual',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tracked_keyword_id, snapshot_date, source)
);
CREATE INDEX IF NOT EXISTS idx_seo_rank_snap_kw ON seo_aeo.seo_rank_snapshots (tracked_keyword_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_cms_targets (
    customer_id     INTEGER PRIMARY KEY,
    cms_type        TEXT NOT NULL DEFAULT 'webhook',
    base_url        TEXT NOT NULL DEFAULT '',
    auth_json       JSONB NOT NULL DEFAULT '{}',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_cms_publish_jobs (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    content_id      INTEGER NOT NULL,
    cms_type        TEXT NOT NULL DEFAULT 'webhook',
    status          TEXT NOT NULL DEFAULT 'pending',
    remote_url      TEXT NOT NULL DEFAULT '',
    payload_json    JSONB NOT NULL DEFAULT '{}',
    response_json   JSONB NOT NULL DEFAULT '{}',
    error_message   TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_seo_cms_jobs_customer ON seo_aeo.seo_cms_publish_jobs (customer_id, status);
