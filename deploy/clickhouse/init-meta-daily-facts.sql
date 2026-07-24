-- Meta daily facts for BI warehouse (B14 / ME48)
CREATE TABLE IF NOT EXISTS ptt.meta_daily_facts (
    client_id UUID,
    channel LowCardinality(String),
    external_campaign_id String,
    performance_date Date,
    spend Float64,
    impressions UInt64,
    clicks UInt64,
    leads_platform UInt32,
    leads_crm UInt32,
    hub_mapped UInt8,
    exported_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(exported_at)
PARTITION BY toYYYYMM(performance_date)
ORDER BY (client_id, channel, performance_date, external_campaign_id)
TTL performance_date + INTERVAL 36 MONTH;
