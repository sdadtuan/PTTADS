-- P0-10 KPI dictionary seed (idempotent) — spec §8
BEGIN;

CREATE TABLE IF NOT EXISTS kpi_definitions (
    code            VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    formula         TEXT NOT NULL,
    source_tables   JSONB NOT NULL DEFAULT '[]'::jsonb,
    granularity     VARCHAR(32) NOT NULL DEFAULT 'day',
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO kpi_definitions (code, name, formula, source_tables, granularity, description) VALUES
    ('SPEND', 'Chi phí quảng cáo', 'SUM(daily_performance.spend)', '["daily_performance"]', 'day', 'Tổng chi phí ads'),
    ('IMPRESSIONS', 'Lượt hiển thị', 'SUM(daily_performance.impressions)', '["daily_performance"]', 'day', NULL),
    ('CLICKS', 'Lượt click', 'SUM(daily_performance.clicks)', '["daily_performance"]', 'day', NULL),
    ('CTR', 'Tỷ lệ click', 'clicks / NULLIF(impressions, 0)', '["daily_performance"]', 'day', NULL),
    ('CPC', 'Chi phí/click', 'spend / NULLIF(clicks, 0)', '["daily_performance"]', 'day', NULL),
    ('CPM', 'CPM', 'spend / NULLIF(impressions, 0) * 1000', '["daily_performance"]', 'day', NULL),
    ('LEADS', 'Số lead', 'COUNT(lead events)', '["crm_leads","tracking_events"]', 'day', NULL),
    ('CPL', 'Chi phí/lead', 'spend / NULLIF(leads, 0)', '["daily_performance","crm_leads"]', 'week', 'Closed-loop Phase 2'),
    ('CPA', 'Chi phí/chuyển đổi', 'spend / NULLIF(conversions, 0)', '["daily_performance"]', 'day', NULL),
    ('ROAS', 'ROAS', 'conversion_value / NULLIF(spend, 0)', '["daily_performance","tracking_events"]', 'week', NULL),
    ('WIN_RATE', 'Tỷ lệ chốt', 'won / NULLIF(qualified, 0)', '["crm_leads"]', 'month', 'CRM KPI'),
    ('SLA_BREACH', 'Vi phạm SLA', 'COUNT(overdue SLA objects)', '["crm_leads","crm_cases"]', 'day', NULL),
    ('FREQUENCY', 'Tần suất hiển thị', 'Meta API frequency', '["daily_performance"]', 'day', 'Meta adset')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    granularity = EXCLUDED.granularity,
    description = EXCLUDED.description;

COMMIT;
