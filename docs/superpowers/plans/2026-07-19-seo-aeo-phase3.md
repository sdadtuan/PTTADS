# Phase 3 — Technical Console, GSC CSV, Reporting, Automation (2026-07-19)

> **Trạng thái:** Implemented (SQLite legacy)  
> **Policy sau Phase 3:** [`specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../../specs/2026-07-19-seo-aeo-pg-cutover-policy.md) — **không build thêm trên SQLite**  
> **Next gate:** [`2026-07-19-seo-aeo-phase3.5-pg-cutover.md`](2026-07-19-seo-aeo-phase3.5-pg-cutover.md)

## Scope (MVP)

- `seo_technical_issues`, `seo_sync_runs`, `seo_gsc_daily_stats`, `seo_alerts` tables
- Technical Console UI + crawl CSV import
- GSC CSV import (Search Console export) + sync run log
- Reporting Center — executive/seo/content/technical/ops dashboards
- Automation rules — critical issues, sync failed, AEO coverage low, content overdue
- Delivery panel + hub alerts extended

## Not in Phase 3

- Live GSC/GA4 OAuth API → **Phase 4 (PostgreSQL only, sau Phase 3.5 cutover)**
- Email/Slack alert delivery
- Auto-create CRM tasks from critical issues

## Routes

| Route | Purpose |
|-------|---------|
| GET `/crm/seo/technical` | Technical Console |
| GET `/crm/seo/reports` | Reporting Center |
| GET `/crm/seo/automations` | Alerts & rules |
| GET/POST `/api/v1/seo/clients/:id/technical/*` | Issues CRUD + import |
| POST `/api/v1/seo/clients/:id/gsc/import` | GSC CSV |
| GET `/api/v1/seo/reports/dashboard` | Dashboard JSON |
| POST `/api/v1/seo/automations/run` | Evaluate rules |

## Tests

`python -m unittest tests.test_seo_aeo_phase3 -v`
