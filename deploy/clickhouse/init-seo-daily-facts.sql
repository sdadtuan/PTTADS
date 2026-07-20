-- SEO daily facts for BI warehouse (Phase 5D)
CREATE TABLE IF NOT EXISTS ptt.seo_daily_facts (
    customer_id UInt32,
    fact_date Date,
    metric_name String,
    metric_value Float64,
    dimensions String,
    exported_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(fact_date)
ORDER BY (customer_id, fact_date, metric_name);
