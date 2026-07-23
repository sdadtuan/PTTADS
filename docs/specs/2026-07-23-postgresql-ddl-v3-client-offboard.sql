-- Wave B7.1-S1 — client offboard audit + tenant lock stub
BEGIN;

ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS tenant_locked BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_clients_tenant_locked ON clients (tenant_locked) WHERE tenant_locked IS TRUE;

CREATE TABLE IF NOT EXISTS client_offboard_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    initiated_by    TEXT NOT NULL,
    reason          VARCHAR(64) NOT NULL,
    note            TEXT,
    tokens_revoked  INT NOT NULL DEFAULT 0,
    portal_users_deactivated INT NOT NULL DEFAULT 0,
    previous_status VARCHAR(32),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_offboard_audit_client
    ON client_offboard_audit (client_id, created_at DESC);

COMMENT ON TABLE client_offboard_audit IS
    'Immutable audit trail when agency offboards a client (Wave B7.1).';

INSERT INTO schema_migrations (version, description)
VALUES ('2026-07-23-v3-client-offboard', 'client_offboard_audit + clients.tenant_locked')
ON CONFLICT (version) DO NOTHING;

COMMIT;
