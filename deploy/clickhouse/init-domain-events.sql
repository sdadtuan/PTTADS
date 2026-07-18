-- Database `ptt` is created by docker-compose CLICKHOUSE_DB=ptt

CREATE TABLE IF NOT EXISTS ptt.domain_events (
    event_id UUID,
    event_type String,
    aggregate_type String,
    aggregate_id String,
    client_id Nullable(UUID),
    payload String,
    idempotency_key String,
    created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (event_type, created_at, event_id);
