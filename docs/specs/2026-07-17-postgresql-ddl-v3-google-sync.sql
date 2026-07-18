-- PTT Agency Platform — Google insights sync watermark (Phase 3 Track G)
BEGIN;

CREATE TABLE IF NOT EXISTS google_insights_sync_state (
    id                  SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sync_at        TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    last_error          TEXT,
    accounts_total      INT NOT NULL DEFAULT 0,
    accounts_failed     INT NOT NULL DEFAULT 0,
    rows_upserted       BIGINT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO google_insights_sync_state (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-google-sync', 'google_insights_sync_state watermark')
ON CONFLICT (version) DO NOTHING;

COMMIT;
