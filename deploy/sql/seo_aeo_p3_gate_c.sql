-- Gate C P3: content Temporal workflow id + report branding notes (PG seo_aeo)

ALTER TABLE seo_aeo.seo_content
    ADD COLUMN IF NOT EXISTS temporal_workflow_id TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_seo_content_temporal_wf
    ON seo_aeo.seo_content (temporal_workflow_id)
    WHERE temporal_workflow_id <> '';
