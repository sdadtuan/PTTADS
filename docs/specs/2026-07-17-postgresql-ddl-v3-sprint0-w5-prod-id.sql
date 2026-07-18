-- Phase 2.1 / Sprint 0 — prod lead id allocator (W5)
-- Apply: ./scripts/apply_pg_ddl_v3_sprint0.sh
-- Prod create uses crm_leads_prod_id_seq (ids < 900M). Staging stub uses >= 900M.

BEGIN;

CREATE SEQUENCE IF NOT EXISTS crm_leads_prod_id_seq AS BIGINT;

SELECT setval(
    'crm_leads_prod_id_seq',
    GREATEST(
        COALESCE(
            (SELECT MAX(sqlite_lead_id) FROM crm_leads WHERE sqlite_lead_id < 900000000),
            0
        ),
        1
    ),
    true
);

COMMENT ON SEQUENCE crm_leads_prod_id_seq IS
    'Prod POST /api/v1/leads id allocator (W5). Staging uses sqlite_lead_id >= 900000000.';

-- Portal client users (AUTH spike — replace with Keycloak Phase 3.1)
CREATE TABLE IF NOT EXISTS portal_client_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(16) NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('viewer', 'approver')),
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_portal_client_users_client
    ON portal_client_users (client_id, active);

COMMENT ON TABLE portal_client_users IS
    'Client portal login (Sprint 0 spike). Password = bcrypt or stub seed only.';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-sprint0', 'W5 prod id seq + portal_client_users')
ON CONFLICT (version) DO NOTHING;

COMMIT;
