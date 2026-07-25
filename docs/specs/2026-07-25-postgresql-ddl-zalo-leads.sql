-- PTT Agency Platform — Zalo lead form poll + events (Wave Z2 / Sprint S3)
BEGIN;

CREATE TABLE IF NOT EXISTS zalo_lead_form_sync_cursor (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    oa_id               VARCHAR(64) NOT NULL,
    form_id             VARCHAR(64) NOT NULL,
    last_form_data_id   VARCHAR(128),
    last_polled_at      TIMESTAMPTZ,
    last_status         VARCHAR(16),
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, oa_id, form_id)
);

CREATE INDEX IF NOT EXISTS idx_zalo_form_cursor_client
    ON zalo_lead_form_sync_cursor (client_id);

CREATE INDEX IF NOT EXISTS idx_zalo_form_cursor_polled
    ON zalo_lead_form_sync_cursor (last_polled_at DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS zalo_lead_events (
    id              BIGSERIAL PRIMARY KEY,
    lead_id         BIGINT REFERENCES crm_leads(sqlite_lead_id) ON DELETE SET NULL,
    client_id       UUID REFERENCES clients(id) ON DELETE SET NULL,
    event_type      VARCHAR(32) NOT NULL,
    payload_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zalo_lead_events_lead
    ON zalo_lead_events (lead_id DESC NULLS LAST)
    WHERE lead_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_zalo_lead_events_client
    ON zalo_lead_events (client_id, created_at DESC NULLS LAST)
    WHERE client_id IS NOT NULL;

INSERT INTO schema_migrations (version, description) VALUES
    ('2026-07-25-zalo-leads', 'zalo_lead_form_sync_cursor + zalo_lead_events')
ON CONFLICT (version) DO NOTHING;

COMMIT;
