-- Portal password reset tokens (GAP-P0-02)
BEGIN;

CREATE TABLE IF NOT EXISTS portal_password_reset_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES portal_client_users (id) ON DELETE CASCADE,
    token_hash      VARCHAR(64) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portal_pwd_reset_user
    ON portal_password_reset_tokens (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_portal_pwd_reset_hash_active
    ON portal_password_reset_tokens (token_hash)
    WHERE used_at IS NULL;

COMMENT ON TABLE portal_password_reset_tokens IS
    'One-time portal password reset tokens (raw token emailed; only SHA-256 hash stored).';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-25-v3-portal-password-reset', 'portal_password_reset_tokens for forgot-password flow')
ON CONFLICT (version) DO NOTHING;

COMMIT;
