-- Phase 3 / Wave B6-S7 — portal client branding settings
BEGIN;

CREATE TABLE IF NOT EXISTS portal_client_settings (
    client_id       UUID PRIMARY KEY REFERENCES clients (id) ON DELETE CASCADE,
    display_name    VARCHAR(255),
    logo_url        TEXT,
    am_contact_name VARCHAR(255),
    am_contact_email VARCHAR(255),
    accent_color    VARCHAR(32),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by      TEXT
);

COMMENT ON TABLE portal_client_settings IS
    'Client-facing portal branding — logo, display name, AM contact.';

INSERT INTO schema_migrations (version, description)
VALUES ('2026-07-23-v3-portal-settings', 'portal_client_settings branding')
ON CONFLICT (version) DO NOTHING;

COMMIT;
