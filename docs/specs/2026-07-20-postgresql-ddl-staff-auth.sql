-- Phase 0 — staff auth + RBAC section permissions (ops-web)
-- Apply: ./scripts/apply_pg_ddl_staff_auth.sh

BEGIN;

CREATE TABLE IF NOT EXISTS staff_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL DEFAULT '',
    position_id     INTEGER NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_staff_users_position
    ON staff_users (position_id, active);

COMMENT ON TABLE staff_users IS
    'Internal staff accounts for ops-web (Phase 0). Keycloak replaces in Phase 3.';

CREATE TABLE IF NOT EXISTS staff_section_permissions (
    id              BIGSERIAL PRIMARY KEY,
    position_id     INTEGER NOT NULL,
    section_id      VARCHAR(64) NOT NULL,
    action          VARCHAR(32) NOT NULL DEFAULT 'view',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (position_id, section_id, action)
);

CREATE INDEX IF NOT EXISTS idx_staff_section_permissions_position
    ON staff_section_permissions (position_id);

COMMENT ON TABLE staff_section_permissions IS
    'RBAC matrix migrated from SQLite crm_position_section_permissions.';

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-20-staff-auth', 'Phase 0 staff auth + section permissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
