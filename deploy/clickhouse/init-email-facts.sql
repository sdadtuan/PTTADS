-- Email Marketing daily facts for BI warehouse (Wave 2)
CREATE TABLE IF NOT EXISTS ptt.email_daily_facts (
    client_id UUID,
    fact_date Date,
    metric_name String,
    metric_value Float64,
    dimensions String,
    exported_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(fact_date)
ORDER BY (client_id, fact_date, metric_name);

CREATE TABLE IF NOT EXISTS ptt.email_deliverability_daily (
    client_id UUID,
    domain String,
    metric_date Date,
    sent_count UInt64,
    delivered_count UInt64,
    bounce_hard UInt64,
    bounce_soft UInt64,
    complaint_count UInt64,
    unsubscribe_count UInt64
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(metric_date)
ORDER BY (client_id, domain, metric_date);
