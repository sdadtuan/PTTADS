# Plan: SEO/AEO Ops Phase 1 Foundation

> **Ngày:** 2026-07-19 · **Trạng thái:** Implemented (SQLite legacy — xem Phase 3.5 cutover)  
> **Policy:** [`specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../../specs/2026-07-19-seo-aeo-pg-cutover-policy.md)  
> **Spec:** [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](../../SPEC_SEO_AEO_OPERATING_SYSTEM.md)

## Mục tiêu Phase 1

- Bounded context `ptt_seo/` (schema, settings, projects, initiatives, hub, delivery)
- Blueprint `blueprints/seo_aeo.py` — `/crm/seo`, client workspace, API v1
- Hub UI mirror Facebook Ads pattern
- Tab delivery trong Service Workflow cho slug SEO/AEO
- RBAC `crm_seo_aeo`, sidebar nav
- Tests `tests/test_seo_aeo_phase1.py`

## Delivered

| Item | Path |
|------|------|
| Package | `ptt_seo/` |
| Blueprint | `blueprints/seo_aeo.py` |
| Hub UI | `templates/crm_seo_hub.html`, `static/crm_seo_hub.js` |
| Client UI | `templates/crm_seo_client.html`, `static/crm_seo_client.js` |
| Workflow panel | `templates/partials/seo_delivery_panel.html` |
| PG schema (future) | `deploy/sql/seo_aeo_pg_schema.sql` |

## Phase 2 next

- Research Console (keywords/questions)
- Content Pipeline kanban
- Approval bridge SEO/AEO stages
