-- Phase 2 P1 — domain_events idempotency_key (catalog.yaml LeadAssigned)
-- Apply after v3 OLTP: ./scripts/apply_pg_ddl_v3_events_idempotency.sh

ALTER TABLE domain_events
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);

CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_events_idempotency_key
    ON domain_events (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-17-v3-ev-idem', 'domain_events.idempotency_key UNIQUE partial index')
ON CONFLICT (version) DO NOTHING;
