-- P3d-f: report schedule CC/BCC (PG seo_aeo schema)

ALTER TABLE seo_aeo.seo_report_schedules
    ADD COLUMN IF NOT EXISTS cc_emails_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE seo_aeo.seo_report_schedules
    ADD COLUMN IF NOT EXISTS bcc_emails_json TEXT NOT NULL DEFAULT '[]';
