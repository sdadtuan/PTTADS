-- EM-1 extension — preference / unsubscribe / confirm tokens
-- Apply: ./scripts/apply_pg_ddl_email_mkt_em1.sh

BEGIN;

CREATE TABLE IF NOT EXISTS email_mkt.preference_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token               VARCHAR(128) NOT NULL UNIQUE,
    contact_id          UUID NOT NULL REFERENCES email_mkt.contacts (id) ON DELETE CASCADE,
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    purpose             VARCHAR(32) NOT NULL DEFAULT 'preferences'
                        CHECK (purpose IN ('preferences', 'unsubscribe', 'confirm')),
    expires_at          TIMESTAMPTZ,
    used_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pref_tokens_contact ON email_mkt.preference_tokens (contact_id);
CREATE INDEX IF NOT EXISTS idx_pref_tokens_client ON email_mkt.preference_tokens (client_id);

INSERT INTO schema_migrations (version, description)
VALUES ('email_mkt_em1', 'Email EM-1 preference tokens + public capture support')
ON CONFLICT (version) DO NOTHING;

COMMIT;
