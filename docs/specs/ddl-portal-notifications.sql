-- Portal client notification center (PROD-P0-NOTIFY / GAP-P1-02)
-- Apply after core DDL (2026-07-17-postgresql-ddl-v1.sql)

CREATE TABLE IF NOT EXISTS portal_notification (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL,
    portal_user_id  UUID,
    category        VARCHAR(32) NOT NULL DEFAULT 'system',
    title           VARCHAR(255) NOT NULL,
    body            TEXT,
    link_url        TEXT,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_notification_client_user
    ON portal_notification (client_id, portal_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_portal_notification_unread
    ON portal_notification (client_id, portal_user_id)
    WHERE read_at IS NULL;

COMMENT ON TABLE portal_notification IS 'Client portal in-app notifications scoped by client_id + optional portal_user_id';
COMMENT ON COLUMN portal_notification.portal_user_id IS 'NULL = visible to all active portal users of client_id';
