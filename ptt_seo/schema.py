"""SQLite schema for SEO/AEO OS — LEGACY (Phase 1–3).

FROZEN 2026-07-19: Do not add new tables/columns here.
New DDL → deploy/sql/seo_aeo_pg_schema.sql
Runtime → ptt_seo/db.py (SEO_AEO_DB=sqlite|pg|dual)
"""
from __future__ import annotations

import sqlite3


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_client_settings (
            customer_id           INTEGER PRIMARY KEY,
            domains_json          TEXT NOT NULL DEFAULT '[]',
            markets_json          TEXT NOT NULL DEFAULT '[]',
            languages_json        TEXT NOT NULL DEFAULT '["vi"]',
            industry              TEXT NOT NULL DEFAULT '',
            brand_guidelines_json TEXT NOT NULL DEFAULT '{}',
            seo_guidelines_json   TEXT NOT NULL DEFAULT '{}',
            aeo_guidelines_json   TEXT NOT NULL DEFAULT '{}',
            contract_tier         TEXT NOT NULL DEFAULT 'standard',
            notes                 TEXT NOT NULL DEFAULT '',
            updated_at            TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            lifecycle_id    INTEGER,
            name            TEXT NOT NULL DEFAULT '',
            project_type    TEXT NOT NULL DEFAULT 'seo',
            status          TEXT NOT NULL DEFAULT 'active',
            start_date      TEXT,
            end_date        TEXT,
            owner_staff_id  INTEGER,
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_projects_customer ON seo_projects (customer_id);
        CREATE INDEX IF NOT EXISTS idx_seo_projects_lifecycle ON seo_projects (lifecycle_id);

        CREATE TABLE IF NOT EXISTS seo_initiatives (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            project_id      INTEGER,
            lifecycle_id    INTEGER,
            title           TEXT NOT NULL DEFAULT '',
            description     TEXT NOT NULL DEFAULT '',
            impact          TEXT NOT NULL DEFAULT 'medium',
            effort          TEXT NOT NULL DEFAULT 'medium',
            roadmap_bucket  TEXT NOT NULL DEFAULT '30d',
            status          TEXT NOT NULL DEFAULT 'planned',
            owner_staff_id  INTEGER,
            deadline        TEXT,
            created_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_initiatives_customer ON seo_initiatives (customer_id);
        CREATE INDEX IF NOT EXISTS idx_seo_initiatives_lifecycle ON seo_initiatives (lifecycle_id);

        CREATE TABLE IF NOT EXISTS seo_keywords (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id       INTEGER NOT NULL,
            phrase            TEXT NOT NULL DEFAULT '',
            volume            INTEGER,
            difficulty        REAL,
            intent            TEXT NOT NULL DEFAULT 'informational',
            business_value    TEXT NOT NULL DEFAULT 'medium',
            cluster_id        INTEGER,
            opportunity_score REAL,
            status            TEXT NOT NULL DEFAULT 'active',
            created_at        TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_keywords_customer ON seo_keywords (customer_id);

        CREATE TABLE IF NOT EXISTS seo_questions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at          TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_questions_customer ON seo_questions (customer_id);

        CREATE TABLE IF NOT EXISTS seo_content (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
            due_date            TEXT,
            publish_date        TEXT,
            brief_json          TEXT NOT NULL DEFAULT '{}',
            outline_json        TEXT NOT NULL DEFAULT '{}',
            body_html           TEXT NOT NULL DEFAULT '',
            seo_score           REAL,
            aeo_score           REAL,
            created_at          TEXT NOT NULL DEFAULT '',
            updated_at          TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_content_customer ON seo_content (customer_id);
        CREATE INDEX IF NOT EXISTS idx_seo_content_status ON seo_content (customer_id, workflow_status);
        CREATE INDEX IF NOT EXISTS idx_seo_content_lifecycle ON seo_content (lifecycle_id);

        CREATE TABLE IF NOT EXISTS seo_content_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id      INTEGER NOT NULL,
            version_number  INTEGER NOT NULL DEFAULT 1,
            body_html       TEXT NOT NULL DEFAULT '',
            changes_summary TEXT NOT NULL DEFAULT '',
            created_by      TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_content_versions ON seo_content_versions (content_id);

        CREATE TABLE IF NOT EXISTS seo_content_approvals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id   INTEGER NOT NULL,
            stage        TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            actor_id     TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_content_approvals ON seo_content_approvals (content_id);

        CREATE TABLE IF NOT EXISTS seo_audit_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  INTEGER,
            entity_type  TEXT NOT NULL DEFAULT '',
            entity_id    INTEGER,
            action       TEXT NOT NULL DEFAULT '',
            actor_id     TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at   TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_audit_customer ON seo_audit_log (customer_id);

        CREATE TABLE IF NOT EXISTS seo_technical_issues (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            url             TEXT NOT NULL DEFAULT '',
            issue_type      TEXT NOT NULL DEFAULT '',
            severity        TEXT NOT NULL DEFAULT 'medium',
            status          TEXT NOT NULL DEFAULT 'detected',
            description     TEXT NOT NULL DEFAULT '',
            impact_notes    TEXT NOT NULL DEFAULT '',
            assignee_id     INTEGER,
            discovered_at   TEXT NOT NULL DEFAULT '',
            resolved_at     TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_seo_issues_customer ON seo_technical_issues (customer_id, status);
        CREATE INDEX IF NOT EXISTS idx_seo_issues_severity ON seo_technical_issues (customer_id, severity);

        CREATE TABLE IF NOT EXISTS seo_sync_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            source          TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'pending',
            started_at      TEXT,
            finished_at     TEXT,
            rows_imported   INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT NOT NULL DEFAULT '',
            payload_json    TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_seo_sync_customer ON seo_sync_runs (customer_id, source);

        CREATE TABLE IF NOT EXISTS seo_gsc_daily_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            stat_date       TEXT NOT NULL DEFAULT '',
            query           TEXT NOT NULL DEFAULT '',
            page            TEXT NOT NULL DEFAULT '',
            clicks          INTEGER NOT NULL DEFAULT 0,
            impressions     INTEGER NOT NULL DEFAULT 0,
            ctr             REAL,
            position        REAL,
            created_at      TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, stat_date, query, page)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_gsc_customer_date ON seo_gsc_daily_stats (customer_id, stat_date);

        CREATE TABLE IF NOT EXISTS seo_ga4_daily_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            stat_date       TEXT NOT NULL DEFAULT '',
            landing_page    TEXT NOT NULL DEFAULT '',
            source_medium   TEXT NOT NULL DEFAULT '',
            sessions        INTEGER NOT NULL DEFAULT 0,
            users           INTEGER NOT NULL DEFAULT 0,
            pageviews       INTEGER NOT NULL DEFAULT 0,
            bounce_rate     REAL,
            avg_session_duration REAL,
            conversions     REAL NOT NULL DEFAULT 0,
            revenue         REAL NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, stat_date, landing_page, source_medium)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_ga4_customer_date ON seo_ga4_daily_stats (customer_id, stat_date);

        CREATE TABLE IF NOT EXISTS seo_ai_mentions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            question_id     INTEGER,
            platform        TEXT NOT NULL DEFAULT 'anthropic_sim',
            query_text      TEXT NOT NULL DEFAULT '',
            source_url      TEXT NOT NULL DEFAULT '',
            citation_status TEXT NOT NULL DEFAULT 'absent',
            brand_visible   INTEGER NOT NULL DEFAULT 0,
            gap_notes       TEXT NOT NULL DEFAULT '',
            ai_response     TEXT NOT NULL DEFAULT '',
            legacy_scan_id  INTEGER,
            detected_at     TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_ai_mentions_customer ON seo_ai_mentions (customer_id, detected_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_seo_ai_mentions_legacy_scan
            ON seo_ai_mentions (legacy_scan_id) WHERE legacy_scan_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS seo_content_freshness (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id       INTEGER NOT NULL,
            content_id        INTEGER NOT NULL,
            decay_score       REAL NOT NULL DEFAULT 0,
            traffic_delta_pct REAL,
            age_days          INTEGER NOT NULL DEFAULT 0,
            signals_json      TEXT NOT NULL DEFAULT '{}',
            refresh_priority  TEXT NOT NULL DEFAULT 'low',
            last_scored_at    TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, content_id)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_freshness_priority ON seo_content_freshness (customer_id, refresh_priority);

        CREATE TABLE IF NOT EXISTS seo_authority_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            signal_type     TEXT NOT NULL DEFAULT 'backlink',
            source_domain   TEXT NOT NULL DEFAULT '',
            source_url      TEXT NOT NULL DEFAULT '',
            target_url      TEXT NOT NULL DEFAULT '',
            anchor_text     TEXT NOT NULL DEFAULT '',
            domain_rating   REAL,
            status          TEXT NOT NULL DEFAULT 'active',
            first_seen_at   TEXT,
            last_seen_at    TEXT,
            notes           TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, signal_type, source_url, target_url)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_authority_customer ON seo_authority_signals (customer_id, signal_type);

        CREATE TABLE IF NOT EXISTS seo_governance_policies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER,
            policy_key      TEXT NOT NULL,
            name            TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            rule_type       TEXT NOT NULL,
            rule_config     TEXT NOT NULL DEFAULT '{}',
            severity        TEXT NOT NULL DEFAULT 'block',
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, policy_key)
        );

        CREATE TABLE IF NOT EXISTS seo_governance_evaluations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            entity_type     TEXT NOT NULL,
            entity_id       INTEGER NOT NULL,
            action          TEXT NOT NULL,
            passed          INTEGER NOT NULL,
            violations_json TEXT NOT NULL DEFAULT '[]',
            evaluated_at    TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_governance_overrides (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id   INTEGER NOT NULL,
            policy_key      TEXT NOT NULL,
            actor_id        TEXT NOT NULL DEFAULT '',
            reason          TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_experiments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            title           TEXT NOT NULL,
            hypothesis      TEXT NOT NULL DEFAULT '',
            experiment_type TEXT NOT NULL DEFAULT 'content',
            target_url      TEXT NOT NULL DEFAULT '',
            content_id      INTEGER,
            status          TEXT NOT NULL DEFAULT 'draft',
            started_at      TEXT,
            ended_at        TEXT,
            owner_id        TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_experiment_variants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id   INTEGER NOT NULL,
            variant_key     TEXT NOT NULL,
            label           TEXT NOT NULL DEFAULT '',
            config_json     TEXT NOT NULL DEFAULT '{}',
            UNIQUE (experiment_id, variant_key)
        );

        CREATE TABLE IF NOT EXISTS seo_experiment_observations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id   INTEGER NOT NULL,
            variant_key     TEXT NOT NULL,
            metric_date     TEXT NOT NULL,
            metric_name     TEXT NOT NULL,
            metric_value    REAL NOT NULL,
            source          TEXT NOT NULL DEFAULT 'manual',
            created_at      TEXT NOT NULL DEFAULT '',
            UNIQUE (experiment_id, variant_key, metric_date, metric_name)
        );

        CREATE TABLE IF NOT EXISTS seo_experiment_decisions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id   INTEGER NOT NULL,
            decision        TEXT NOT NULL,
            rationale       TEXT NOT NULL DEFAULT '',
            decided_by      TEXT NOT NULL DEFAULT '',
            decided_at      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_portal_client_map (
            client_id       TEXT PRIMARY KEY,
            customer_id     INTEGER NOT NULL UNIQUE,
            active          INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER,
            alert_type      TEXT NOT NULL DEFAULT '',
            severity        TEXT NOT NULL DEFAULT 'warn',
            message         TEXT NOT NULL DEFAULT '',
            link            TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'open',
            created_at      TEXT NOT NULL DEFAULT '',
            resolved_at     TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_seo_alerts_status ON seo_alerts (status, created_at);
        """
    )
    _migrate_phase3(conn)
    _migrate_aeo_cutover(conn)


def _migrate_aeo_cutover(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_questions)")}
    additions = [
        ("legacy_aeo_query_id", "INTEGER"),
        ("brand_name", "TEXT NOT NULL DEFAULT ''"),
        ("lifecycle_id", "INTEGER"),
        ("notes", "TEXT NOT NULL DEFAULT ''"),
    ]
    for name, ddl in additions:
        if name not in cols:
            conn.execute(f"ALTER TABLE seo_questions ADD COLUMN {name} {ddl}")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_seo_questions_legacy_aeo
        ON seo_questions (legacy_aeo_query_id) WHERE legacy_aeo_query_id IS NOT NULL
        """
    )
    mention_cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_ai_mentions)")}
    if not mention_cols:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS seo_ai_mentions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id     INTEGER NOT NULL,
                question_id     INTEGER,
                platform        TEXT NOT NULL DEFAULT 'anthropic_sim',
                query_text      TEXT NOT NULL DEFAULT '',
                source_url      TEXT NOT NULL DEFAULT '',
                citation_status TEXT NOT NULL DEFAULT 'absent',
                brand_visible   INTEGER NOT NULL DEFAULT 0,
                gap_notes       TEXT NOT NULL DEFAULT '',
                ai_response     TEXT NOT NULL DEFAULT '',
                legacy_scan_id  INTEGER,
                detected_at     TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_seo_ai_mentions_customer
                ON seo_ai_mentions (customer_id, detected_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_seo_ai_mentions_legacy_scan
                ON seo_ai_mentions (legacy_scan_id) WHERE legacy_scan_id IS NOT NULL;
            """
        )
    conn.commit()


def _migrate_phase3(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_client_settings)")}
    if "integrations_json" not in cols:
        conn.execute(
            "ALTER TABLE seo_client_settings ADD COLUMN integrations_json TEXT NOT NULL DEFAULT '{}'"
        )
    conn.commit()
