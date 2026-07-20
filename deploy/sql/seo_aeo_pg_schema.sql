-- SEO/AEO Enterprise OS — PostgreSQL schema (SOURCE OF TRUTH for new DDL)
-- Apply: psql "$DATABASE_URL" -f deploy/sql/seo_aeo_pg_schema.sql
-- Or: ensure_pg_schema() via ptt_seo/pg_schema.py when SEO_AEO_DB=pg|dual
--
-- POLICY (2026-07-19): Do NOT add new seo_* tables to SQLite (ptt_seo/schema.py).

CREATE SCHEMA IF NOT EXISTS seo_aeo;

CREATE TABLE IF NOT EXISTS seo_aeo.seo_client_settings (
    customer_id             INTEGER PRIMARY KEY,
    domains_json            JSONB NOT NULL DEFAULT '[]',
    markets_json            JSONB NOT NULL DEFAULT '[]',
    languages_json          JSONB NOT NULL DEFAULT '["vi"]',
    industry                TEXT NOT NULL DEFAULT '',
    brand_guidelines_json   JSONB NOT NULL DEFAULT '{}',
    seo_guidelines_json     JSONB NOT NULL DEFAULT '{}',
    aeo_guidelines_json     JSONB NOT NULL DEFAULT '{}',
    contract_tier           TEXT NOT NULL DEFAULT 'standard',
    notes                   TEXT NOT NULL DEFAULT '',
    integrations_json       JSONB NOT NULL DEFAULT '{}',
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_projects (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    lifecycle_id    INTEGER,
    name            TEXT NOT NULL DEFAULT '',
    project_type    TEXT NOT NULL DEFAULT 'seo',
    status          TEXT NOT NULL DEFAULT 'active',
    start_date      DATE,
    end_date        DATE,
    owner_staff_id  INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_projects_customer ON seo_aeo.seo_projects (customer_id);
CREATE INDEX IF NOT EXISTS idx_seo_projects_lifecycle ON seo_aeo.seo_projects (lifecycle_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_initiatives (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    project_id      INTEGER REFERENCES seo_aeo.seo_projects(id),
    lifecycle_id    INTEGER,
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    impact          TEXT NOT NULL DEFAULT 'medium',
    effort          TEXT NOT NULL DEFAULT 'medium',
    roadmap_bucket  TEXT NOT NULL DEFAULT '30d',
    status          TEXT NOT NULL DEFAULT 'planned',
    owner_staff_id  INTEGER,
    deadline        DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_initiatives_customer ON seo_aeo.seo_initiatives (customer_id);
CREATE INDEX IF NOT EXISTS idx_seo_initiatives_lifecycle ON seo_aeo.seo_initiatives (lifecycle_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_keywords (
    id                SERIAL PRIMARY KEY,
    customer_id       INTEGER NOT NULL,
    phrase            TEXT NOT NULL DEFAULT '',
    volume            INTEGER,
    difficulty        REAL,
    intent            TEXT NOT NULL DEFAULT 'informational',
    business_value    TEXT NOT NULL DEFAULT 'medium',
    cluster_id        INTEGER,
    opportunity_score REAL,
    status            TEXT NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_keywords_customer ON seo_aeo.seo_keywords (customer_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_questions (
    id                  SERIAL PRIMARY KEY,
    customer_id         INTEGER NOT NULL,
    question_text       TEXT NOT NULL DEFAULT '',
    intent              TEXT NOT NULL DEFAULT 'informational',
    funnel_stage        TEXT NOT NULL DEFAULT 'awareness',
    source              TEXT NOT NULL DEFAULT 'manual',
    answer_score        REAL,
    status              TEXT NOT NULL DEFAULT 'active',
    legacy_aeo_query_id INTEGER,
    brand_name          TEXT NOT NULL DEFAULT '',
    lifecycle_id        INTEGER,
    notes               TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_questions_customer ON seo_aeo.seo_questions (customer_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_content (
    id                  SERIAL PRIMARY KEY,
    customer_id         INTEGER NOT NULL,
    project_id          INTEGER,
    lifecycle_id        INTEGER,
    title               TEXT NOT NULL DEFAULT '',
    slug                TEXT NOT NULL DEFAULT '',
    content_type        TEXT NOT NULL DEFAULT 'blog',
    workflow_status     TEXT NOT NULL DEFAULT 'idea',
    target_keyword_id   INTEGER,
    target_question_id  INTEGER,
    intent              TEXT NOT NULL DEFAULT '',
    funnel_stage        TEXT NOT NULL DEFAULT '',
    owner_staff_id      INTEGER,
    due_date            DATE,
    publish_date        DATE,
    brief_json          JSONB NOT NULL DEFAULT '{}',
    outline_json        JSONB NOT NULL DEFAULT '{}',
    body_html           TEXT NOT NULL DEFAULT '',
    seo_score           REAL,
    aeo_score           REAL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_content_customer ON seo_aeo.seo_content (customer_id);
CREATE INDEX IF NOT EXISTS idx_seo_content_status ON seo_aeo.seo_content (customer_id, workflow_status);
CREATE INDEX IF NOT EXISTS idx_seo_content_lifecycle ON seo_aeo.seo_content (lifecycle_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_content_versions (
    id              SERIAL PRIMARY KEY,
    content_id      INTEGER NOT NULL,
    version_number  INTEGER NOT NULL DEFAULT 1,
    body_html       TEXT NOT NULL DEFAULT '',
    changes_summary TEXT NOT NULL DEFAULT '',
    created_by      TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_content_versions ON seo_aeo.seo_content_versions (content_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_content_approvals (
    id           SERIAL PRIMARY KEY,
    content_id   INTEGER NOT NULL,
    stage        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    actor_id     TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_content_approvals ON seo_aeo.seo_content_approvals (content_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_audit_log (
    id           SERIAL PRIMARY KEY,
    customer_id  INTEGER,
    entity_type  TEXT NOT NULL DEFAULT '',
    entity_id    INTEGER,
    action       TEXT NOT NULL DEFAULT '',
    actor_id     TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_audit_customer ON seo_aeo.seo_audit_log (customer_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_technical_issues (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    url             TEXT NOT NULL DEFAULT '',
    issue_type      TEXT NOT NULL DEFAULT '',
    severity        TEXT NOT NULL DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'detected',
    description     TEXT NOT NULL DEFAULT '',
    impact_notes    TEXT NOT NULL DEFAULT '',
    assignee_id     INTEGER,
    discovered_at   TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_seo_issues_customer ON seo_aeo.seo_technical_issues (customer_id, status);
CREATE INDEX IF NOT EXISTS idx_seo_issues_severity ON seo_aeo.seo_technical_issues (customer_id, severity);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_sync_runs (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    source          TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    rows_imported   INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT NOT NULL DEFAULT '',
    payload_json    JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_seo_sync_customer ON seo_aeo.seo_sync_runs (customer_id, source);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_gsc_daily_stats (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    stat_date       DATE NOT NULL,
    query           TEXT NOT NULL DEFAULT '',
    page            TEXT NOT NULL DEFAULT '',
    clicks          INTEGER NOT NULL DEFAULT 0,
    impressions     INTEGER NOT NULL DEFAULT 0,
    ctr             REAL,
    position        REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, stat_date, query, page)
);
CREATE INDEX IF NOT EXISTS idx_seo_gsc_customer_date ON seo_aeo.seo_gsc_daily_stats (customer_id, stat_date);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_ga4_daily_stats (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    stat_date       DATE NOT NULL,
    landing_page    TEXT NOT NULL DEFAULT '',
    source_medium   TEXT NOT NULL DEFAULT '',
    sessions        INTEGER NOT NULL DEFAULT 0,
    users           INTEGER NOT NULL DEFAULT 0,
    pageviews       INTEGER NOT NULL DEFAULT 0,
    bounce_rate     REAL,
    avg_session_duration REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, stat_date, landing_page, source_medium)
);
CREATE INDEX IF NOT EXISTS idx_seo_ga4_customer_date ON seo_aeo.seo_ga4_daily_stats (customer_id, stat_date);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_ai_mentions (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    question_id     INTEGER,
    platform        TEXT NOT NULL DEFAULT 'anthropic_sim',
    query_text      TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    citation_status TEXT NOT NULL DEFAULT 'absent',
    brand_visible   BOOLEAN NOT NULL DEFAULT FALSE,
    gap_notes       TEXT NOT NULL DEFAULT '',
    ai_response     TEXT NOT NULL DEFAULT '',
    legacy_scan_id  INTEGER,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_seo_ai_mentions_customer ON seo_aeo.seo_ai_mentions (customer_id, detected_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_seo_ai_mentions_legacy_scan ON seo_aeo.seo_ai_mentions (legacy_scan_id) WHERE legacy_scan_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS seo_aeo.seo_content_freshness (
    id                SERIAL PRIMARY KEY,
    customer_id       INTEGER NOT NULL,
    content_id        INTEGER NOT NULL,
    decay_score       REAL NOT NULL DEFAULT 0,
    traffic_delta_pct REAL,
    age_days          INTEGER NOT NULL DEFAULT 0,
    signals_json      JSONB NOT NULL DEFAULT '{}',
    refresh_priority  TEXT NOT NULL DEFAULT 'low',
    last_scored_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, content_id)
);
CREATE INDEX IF NOT EXISTS idx_seo_freshness_priority ON seo_aeo.seo_content_freshness (customer_id, refresh_priority);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_authority_signals (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    signal_type     TEXT NOT NULL DEFAULT 'backlink',
    source_domain   TEXT NOT NULL DEFAULT '',
    source_url      TEXT NOT NULL DEFAULT '',
    target_url      TEXT NOT NULL DEFAULT '',
    anchor_text     TEXT NOT NULL DEFAULT '',
    domain_rating   REAL,
    status          TEXT NOT NULL DEFAULT 'active',
    first_seen_at   DATE,
    last_seen_at    DATE,
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, signal_type, source_url, target_url)
);
CREATE INDEX IF NOT EXISTS idx_seo_authority_customer ON seo_aeo.seo_authority_signals (customer_id, signal_type);

-- Phase 5A — Governance
CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_policies (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER,
    policy_key      VARCHAR(64) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    rule_type       VARCHAR(32) NOT NULL,
    rule_config     JSONB NOT NULL DEFAULT '{}',
    severity        VARCHAR(16) NOT NULL DEFAULT 'block',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (customer_id, policy_key)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_evaluations (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    entity_type     VARCHAR(32) NOT NULL,
    entity_id       INTEGER NOT NULL,
    action          VARCHAR(32) NOT NULL,
    passed          BOOLEAN NOT NULL,
    violations_json JSONB NOT NULL DEFAULT '[]',
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_gov_eval_entity
    ON seo_aeo.seo_governance_evaluations (customer_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_governance_overrides (
    id              SERIAL PRIMARY KEY,
    evaluation_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_governance_evaluations(id),
    policy_key      VARCHAR(64) NOT NULL,
    actor_id        TEXT NOT NULL DEFAULT '',
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Phase 5B — Experimentation
CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiments (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    title           VARCHAR(255) NOT NULL,
    hypothesis      TEXT NOT NULL DEFAULT '',
    experiment_type VARCHAR(32) NOT NULL DEFAULT 'content',
    target_url      TEXT NOT NULL DEFAULT '',
    content_id      INTEGER REFERENCES seo_aeo.seo_content(id),
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    owner_id        TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_variants (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    variant_key     VARCHAR(16) NOT NULL,
    label           VARCHAR(255) NOT NULL DEFAULT '',
    config_json     JSONB NOT NULL DEFAULT '{}',
    UNIQUE (experiment_id, variant_key)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_observations (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    variant_key     VARCHAR(16) NOT NULL,
    metric_date     DATE NOT NULL,
    metric_name     VARCHAR(64) NOT NULL,
    metric_value    DOUBLE PRECISION NOT NULL,
    source          VARCHAR(32) NOT NULL DEFAULT 'manual',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (experiment_id, variant_key, metric_date, metric_name)
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_experiment_decisions (
    id              SERIAL PRIMARY KEY,
    experiment_id   INTEGER NOT NULL REFERENCES seo_aeo.seo_experiments(id) ON DELETE CASCADE,
    decision        VARCHAR(32) NOT NULL,
    rationale       TEXT NOT NULL DEFAULT '',
    decided_by      TEXT NOT NULL DEFAULT '',
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Phase 5C — Portal bridge
CREATE TABLE IF NOT EXISTS seo_aeo.seo_portal_client_map (
    client_id       UUID PRIMARY KEY,
    customer_id     INTEGER NOT NULL UNIQUE,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_aeo_scan_runs (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    queries_total   INTEGER NOT NULL DEFAULT 0,
    queries_done    INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS seo_aeo.seo_alerts (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER,
    alert_type      TEXT NOT NULL DEFAULT '',
    severity        TEXT NOT NULL DEFAULT 'warn',
    message         TEXT NOT NULL DEFAULT '',
    link            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_seo_alerts_status ON seo_aeo.seo_alerts (status, created_at);
