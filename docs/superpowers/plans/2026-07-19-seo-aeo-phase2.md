# Plan: SEO/AEO Ops Phase 2 — Research & Content Pipeline

> **Ngày:** 2026-07-19 · **Trạng thái:** Implemented (SQLite legacy — xem Phase 3.5 cutover)  
> **Policy:** [`specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../../specs/2026-07-19-seo-aeo-pg-cutover-policy.md)  
> **Depends on:** [Phase 1](2026-07-19-seo-aeo-phase1.md)

## Deliverables

| Module | Path | Spec |
|--------|------|------|
| Keywords & questions | `ptt_seo/research.py` | 6.3 Research |
| Content pipeline | `ptt_seo/content.py` | 6.4 Content Factory |
| Approvals | `ptt_seo/workflow.py` | 6.11 Workflow |
| Research UI | `/crm/seo/research` | Research Console |
| Pipeline UI | `/crm/seo/content` | Content Pipeline kanban |
| Content detail | `/crm/seo/content/:id` | Brief, body, approvals |

## API

- `GET/POST /api/v1/seo/clients/:id/keywords`
- `POST /api/v1/seo/clients/:id/keywords/import`
- `GET/POST /api/v1/seo/clients/:id/questions`
- `POST /api/v1/seo/research/to-content`
- `GET /api/v1/seo/content/pipeline`
- `POST /api/v1/seo/content/:id/status`, `/approve`, `/versions`

## Phase 3 next

- Technical Console + GSC sync
- Reporting dashboards
- AI brief generation (Anthropic)
