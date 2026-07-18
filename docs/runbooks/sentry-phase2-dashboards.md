# Runbook — Sentry dashboards Phase 2

> **Mục tiêu:** Dashboards theo dõi Nest write, Meta sync, CAPI — PRD Phase 2 DoD §10 cross-cutting.

## Prerequisites

```bash
# .env (Flask + Nest + worker)
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production   # hoặc staging
```

Nest `services/ptt-crm-api`: cùng `SENTRY_DSN` trong service env.

## Projects đề xuất

| Project | Components |
|---------|------------|
| `ptt-crm-api` | NestJS leads write |
| `ptt-flask` | Flask proxy, Agency Ops |
| `ptt-worker` | ingest, meta_insights, capi_dispatch, shadow |

## Dashboard 1 — Nest write cutover

**Widgets (Discover / Issues):**

| Widget | Query |
|--------|-------|
| Write 5xx rate | `event.type:error project:ptt-crm-api transaction:*leads*` |
| PATCH p95 latency | `transaction:/api/v1/leads/*` percentile p95 |
| LeadAssigned lag | Custom metric từ cron SQL (optional) |

**Tags to filter:**

- `correlation_id`
- `environment:production`

**Alert:** Error rate > 0.1% trong 15 phút → Slack `#ptt-ops`

## Dashboard 2 — Meta insights sync

| Widget | Query |
|--------|-------|
| Insights sync warnings | `message:*Meta insights sync fail*` |
| Token refresh failures | `category:meta_token OR message:*token*` |

Code path: `ptt_meta.insights_sync._dispatch_insights_sync_alert` → `capture_message` level=warning.

**Alert:** ≥1 warning / ngày trên prod → AM inbox (đã có `notify_agency_ops`).

## Dashboard 3 — CAPI dispatch

| Widget | Query |
|--------|-------|
| CAPI failed | `message:*capi dispatch failed*` |
| Graph errors | `meta_response.error` in breadcrumbs (if enabled) |

Target pilot: error rate < 5% (`capi_event_log.status = failed`).

SQL cron check (daily):

```bash
psql "$DATABASE_URL" -c "
  SELECT status, COUNT(*) FROM capi_event_log
  WHERE created_at >= NOW() - INTERVAL '24 hours'
  GROUP BY 1;
"
```

## Dashboard 4 — Write dual-run / shadow

Flask/worker emits on mismatch (see `ptt_crm.dual_run.py`):

| Widget | Query |
|--------|-------|
| Dual-run mismatch | `message:*dual_run_mismatch*` |

## Setup steps (Sentry UI)

1. **Settings → Projects** — tạo/ chọn `ptt-crm-api`, `ptt-flask`, `ptt-worker`
2. **Dashboards → Create Dashboard** — "Phase 2 Write + Meta"
3. Add widgets từ bảng trên (Issues + Discover)
4. **Alerts → Create Alert** — threshold theo PRD §11
5. Link dashboard vào runbook [cutover-leads-write-phase2.md](./cutover-leads-write-phase2.md) §6

## Staging verification

```bash
# Trigger test event (staging only)
python3 -c "
import os
os.environ.setdefault('SENTRY_DSN', os.environ.get('SENTRY_DSN',''))
import sentry_sdk
sentry_sdk.init(dsn=os.environ['SENTRY_DSN'], environment='staging')
sentry_sdk.capture_message('phase2_sentry_dashboard_test', level='info')
print('OK sent test event')
"
```

## Checklist DoD

- [ ] Dashboard "Phase 2 Write + Meta" created
- [ ] Alerts: Nest write 5xx, insights sync fail, CAPI fail rate
- [ ] `SENTRY_ENVIRONMENT` set per VPS (staging / production)
- [ ] Linked in Phase 2 sign-off ([phase2-uat-signoff.md](./phase2-uat-signoff.md))

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Phase 2 Sentry dashboards runbook |
