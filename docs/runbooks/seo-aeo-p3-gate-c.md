# SEO/AEO — Gate C P3 implementation runbook

## Scope shipped (Gate C)

| Hạng mục | Module | Env / flag |
|----------|--------|------------|
| SerpAPI / DataForSEO | `ptt_seo/serp_provider.py` | `PTT_SERP_PROVIDER=serpapi\|dataforseo`, `SERPAPI_API_KEY` or `DATAFORSEO_LOGIN`/`PASSWORD` |
| White-label PDF | `ptt_seo/report_branding.py`, `report_export.py` | `seo_client_settings.brand_guidelines` |
| Portal widgets | `ptt_seo/portal_widgets.py` | `GET /api/v1/seo/internal/portal/widgets` |
| Entity graph UI+ | Research drawer filter/link/detail | Enterprise flag |
| Temporal content WF | `SeoContentApprovalWorkflow` | `PTT_SEO_CONTENT_TEMPORAL=1`, `PTT_TEMPORAL_ADDRESS` |

## SERP provider

```bash
# Stub (default)
export PTT_SERP_PROVIDER=stub

# SerpAPI
export PTT_SERP_PROVIDER=serpapi
export SERPAPI_API_KEY=<key>

# DataForSEO
export PTT_SERP_PROVIDER=dataforseo
export DATAFORSEO_LOGIN=<login>
export DATAFORSEO_PASSWORD=<password>
```

Capture: `POST /api/v1/seo/clients/:id/research/serp/capture` body `{ "phrase": "...", "location": "Vietnam", "language": "vi" }`.

Missing API keys → auto fallback stub (logged in response `provider_configured`).

## Report white-label

Set trong CRM → Client SEO settings → `brand_guidelines` JSON:

```json
{
  "company_name": "Client X",
  "primary_color": "#059669",
  "report_title_prefix": "Monthly SEO Report",
  "report_footer": "Confidential — Client X only",
  "hide_agency_branding": true
}
```

PDF export: `GET /api/v1/seo/reports/export.pdf?customer_id=N&type=executive`

## Portal widgets

Internal (Nest → Flask):

`GET /api/v1/seo/internal/portal/widgets?client_id=<UUID>`  
Header: `Authorization: Bearer $PTT_PORTAL_SEO_SERVICE_TOKEN`

Portal-web: `/seo` renders `SeoWidgetsPanel` via `GET /api/v1/portal/seo/widgets` (JWT).

Returns KPI cards: GSC clicks sparkline, critical issues, AEO coverage, pending review.

## Temporal content pipeline

1. Enable: `PTT_SEO_CONTENT_TEMPORAL=1`
2. Restart: `ptt-temporal-worker` (registers `SeoContentApprovalWorkflow`)
3. Content → `client_review` starts workflow `seo-content-{id}`
4. Portal approve/reject signals workflow; AM notified via `notification_inbox`

DDL: `deploy/sql/seo_aeo_p3_gate_c.sql` — column `seo_content.temporal_workflow_id`.

## Deploy checklist

- [ ] Apply PG DDL: `seo_aeo_p3_gate_c.sql`
- [ ] Configure SERP keys (optional)
- [ ] Pilot brand_guidelines on 1 client PDF
- [ ] Enable Temporal flag on staging; E2E portal content review
- [x] Portal-web `/seo` — `SeoWidgetsPanel` + `GET /api/v1/portal/seo/widgets`

## Rollback

- SERP: `PTT_SERP_PROVIDER=stub`
- Temporal: `PTT_SEO_CONTENT_TEMPORAL=0` — CRM approve vẫn hoạt động
- White-label: clear brand_guidelines → default PTT styling
