# Gate E — Enterprise depth runbook

Gate E extends SEO/AEO Ops with OKR/KPI tree, scheduled crawl connector, CWV CRM UI, entity auto-link, CMS auto-publish, live rank/SOV, organic revenue attribution, and a11y improvements.

## E1 — OKR/KPI tree

- Tables: `seo_strategy_goals`, `seo_strategy_kpis`, `seo_initiatives.goal_id`
- API: `GET /api/v1/seo/clients/:id/strategy/okr`
- UI: `/crm/seo/strategy` — goal tree + refresh KPI from live metrics

## E2 — Crawl connector

- Table: `seo_crawl_schedules`
- Configure: Technical Console → Crawl connector
- Ingest: `POST /api/v1/seo/internal/crawl-ingest/:customer_id` with header `X-PTT-Crawl-Secret`
- Cron: included in weekly cron + `POST /api/v1/seo/cron/gate-e`

Env:

- `PTT_CRAWL_CONNECTOR_ENABLED=1` (default)

## E3 — CWV dashboard (CRM)

- API: `GET /api/v1/seo/clients/:id/cwv`
- UI: Technical Console → Core Web Vitals panel
- Data from Gate D `seo_cwv_snapshots`

## E4 — Entity auto-link

- `POST /api/v1/seo/clients/:id/entities/autolink`
- Research Console → **Auto-link clusters**

## E5 — CMS auto-publish

- Env: `PTT_SEO_CMS_AUTO_PUBLISH=1`
- Triggers `queue_publish` when content transitions to `published` and CMS target is active

## E6 — Rank live + SOV

- API: `GET .../ranks/sov`, `POST .../ranks/capture`
- UI: Rank Tracker — SOV cards + Capture SERP
- Cron: `PTT_RANK_LIVE_ENABLED=1` in gate-e bundle

## E7 — Organic revenue attribution

- GA4 columns: `conversions`, `revenue` on `seo_ga4_daily_stats`
- API: `GET /api/v1/seo/clients/:id/attribution`
- BI fact: `organic_revenue` in ClickHouse export

## E8 — Accessibility

- `crm_seo_a11y.js` — modal focus trap, Escape close, kanban arrow keys
- `crm_seo_charts.js` — collapsible data table fallback for spark charts

## Schema apply

```bash
bash scripts/apply_seo_gate_e_schema.sh
```

## Staging deploy (schema + CMS auto-publish)

Từ máy có SSH tới staging VPS (thay `<STAGING_HOST>` bằng IP/hostname thật):

```bash
# Dry-run: merge env + apply DDL
PTT_VPS_HOST=<STAGING_HOST> APPLY=0 ./scripts/staging_seo_gate_e_deploy.sh

# Code chưa push git
LOCAL_SYNC=1 PTT_VPS_HOST=<STAGING_HOST> APPLY=0 ./scripts/staging_seo_gate_e_deploy.sh

# Apply + restart Flask + seed CMS pilot client
LOCAL_SYNC=1 PTT_VPS_HOST=<STAGING_HOST> APPLY=1 PILOT_CUSTOMER_ID=1 ./scripts/staging_seo_gate_e_deploy.sh
```

Env mẫu: `deploy/env.staging-seo-gate-e.example` (`PTT_SEO_CMS_AUTO_PUBLISH=1`, enterprise + crawl/rank flags).

Trên VPS trực tiếp (nếu đã có code):

```bash
cd /var/www/ptt
./scripts/apply_seo_gate_e_schema.sh
grep PTT_SEO_CMS_AUTO_PUBLISH .env
sudo systemctl restart ptt
python3 scripts/seed_cms_webhook_pilot.py --customer-id <CRM_ID>
```

## Cron

```bash
curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  http://127.0.0.1:5000/api/v1/seo/cron/gate-e
```
