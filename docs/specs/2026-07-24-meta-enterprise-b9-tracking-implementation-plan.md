# Meta Enterprise — Implementation Plan: B9 Tracking (Conversion OS)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-24  
> **Phạm vi:** CAPI full pipeline, conversion rules, tracking health UI/API, Launch QA Meta gate, insights archive  
> **Nguồn:**  
> - [`../SPEC_META_ENTERPRISE_PTTADS.md`](../SPEC_META_ENTERPRISE_PTTADS.md) v1.2.1 §8.3–8.4, §10.3, §13.1, §18 B9  
> - [`2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](2026-07-24-meta-enterprise-ui-ux-architecture-design.md) §7.3, Phase 2  
> - [`2026-07-24-meta-enterprise-phase0-b8-implementation-plan.md`](2026-07-24-meta-enterprise-phase0-b8-implementation-plan.md) (format reference)  
> **Ước lượng:** ~4–5 tuần (2 dev parallel: backend/Python + frontend) · soak pilot ≥30d trước widen prod

---

## Mục lục

1. [Tổng quan & hiện trạng](#1-tổng-quan--hiện-trạng)
2. [Definition of Done](#2-definition-of-done)
3. [Tiên quyết & phụ thuộc](#3-tiên-quyết--phụ-thuộc)
4. [B9 Backend — DDL & schema (~2 ngày)](#4-b9-backend--ddl--schema-2-ngày)
5. [B9 Python — Conversion engine (~5–7 ngày)](#5-b9-python--conversion-engine-57-ngày)
6. [B9 Nest — meta-tracking API (~5–7 ngày)](#6-b9-nest--meta-tracking-api-57-ngày)
7. [B9 Launch QA Meta gate (~2–3 ngày)](#7-b9-launch-qa-meta-gate-23-ngày)
8. [B9 ops-web — `/meta/tracking` UI (~4–5 ngày)](#8-b9-ops-web--meta-tracking-ui-45-ngày)
9. [B9 Alerts extend (~1–2 ngày)](#9-b9-alerts-extend-12-ngày)
10. [B9 Gates, tests & deploy (~2–3 ngày)](#10-b9-gates-tests--deploy-23-ngày)
11. [Ma trận phụ thuộc file](#11-ma-trận-phụ-thuộc-file)
12. [Feature flags & env](#12-feature-flags--env)
13. [Pilot rollout & soak](#13-pilot-rollout--soak)
14. [Checklist sprint (copy sang board)](#14-checklist-sprint-copy-sang-board)

---

## 1. Tổng quan & hiện trạng

### 1.1. Mục tiêu B9

Chuyển CAPI từ **pilot Lead-only** sang **Conversion OS** đầy đủ:

| Khả năng | Trạng thái hiện tại | B9 target |
|----------|---------------------|-----------|
| Webhook lead → CAPI `Lead` | ✅ `ptt_meta/capi_dispatch.py` + job `capi_dispatch` | Giữ + chuẩn hóa `event_id` |
| CRM status → conversion events | ❌ | `qualified` → `CompleteRegistration`, `post_sale` → `Purchase` |
| Rules engine PG | ❌ | `meta_conversion_rules` + `evaluate_conversion_rules()` |
| Backfill status changes | ❌ | Cron `meta_conversion_sync` (72h lookback) |
| Tracking health API/UI | ❌ | sent/failed/skipped 7d, match hint, latency |
| CAPI events log + retry | ❌ API | `GET /meta/capi/events`, retry, flush |
| Pixel test (Graph probe) | ❌ | `POST .../test-pixel` |
| Launch QA Meta gate | partial (checklist JSONB generic) | pixel · CAPI test · hub map hard items |
| Insights archive | ❌ | `insights_archive` job dry-run + purge >400d |
| Alerts CAPI | ❌ | `capi_fail_rate`, `pixel_missing`, `capi_stale` |
| ops-web `/meta/tracking` | ❌ | Full page + nav |
| `MetaPreflightChecklist` | ❌ | Reuse B15 ads-ops wizard |

### 1.2. Thứ tự thực thi (4 sprint)

```text
Sprint E — B9 Backend foundation (tuần 1)
├── [B9-BE-1] DDL v5 meta_conversion_rules + pg_schema + apply script
├── [B9-BE-2] conversion_rules.py + capi_dispatch extend (event_id convention)
└── [B9-BE-3] Nest meta-tracking module (health + events read + test-pixel)

Sprint F — B9 Conversion pipeline (tuần 2)
├── [B9-PY-1] conversion_sync.py + job handler + worker hook
├── [B9-PY-2] tracking_health.py + insights_archive.py
├── [B9-N-1] conversion-rules CRUD + capi retry/flush
└── [B9-N-2] Hook Nest lead patch → enqueue conversion eval

Sprint G — B9 UI + Launch QA (tuần 3)
├── [B9-FE-1] /meta/tracking page + components
├── [B9-FE-2] MetaPreflightChecklist + hub CAPI badge
├── [B9-LQ-1] Launch QA Meta checklist items + launch_ready gate
└── [B9-FE-3] OpsNav + cap `meta.tracking_view`

Sprint H — B9 QA & pilot (tuần 4–5)
├── [B9-QA-1] wave_b9_gates.py + tests
├── [B9-QA-2] Playwright E2E-M4 (test pixel)
├── [B9-QA-3] Pilot 1–2 clients PTT_CAPI_ENABLED=1
└── [B9-QA-4] Soak 30d → widen + B8 regression
```

### 1.3. Quy tắc merge

| Wave | Merge khi |
|------|-----------|
| **B9** | `wave_b9_gates.py` PASS · §18 B9 acceptance · `wave_b8_gates.py` regression · H1 pytest meta pass |

**Additive:** không thay route/API B8; mở rộng hub badge + tab Tracking link (optional embed sau).

---

## 2. Definition of Done

Theo [`SPEC_META_ENTERPRISE_PTTADS.md`](../SPEC_META_ENTERPRISE_PTTADS.md) §18 B9:

- [ ] Webhook lead → CAPI `Lead` trong Events Manager **<5 phút** (pilot client, non-stub)
- [ ] Lead status `qualified` → `CompleteRegistration` theo rule enabled
- [ ] Tracking tab: sent/failed/skipped 7d; **Test pixel** trả OK trên account có pixel
- [ ] Alert `capi_fail_rate` fire trên synthetic failures (>10% / 24h)
- [ ] Archive job **dry-run** log rows `daily_performance` >400d
- [ ] Launch QA: không `launch_ready` khi thiếu pixel / CAPI test fail / map coverage thấp
- [ ] Prod widen sau **≥30d pilot soak** (khuyến nghị trước B10)

---

## 3. Tiên quyết & phụ thuộc

### 3.1. Bắt buộc trước B9

| Item | Verify |
|------|--------|
| B8 merged | `wave_b8_gates.py` PASS |
| PG v3 performance | `capi_event_log`, `daily_performance`, `hub_campaign_map` |
| PG v4 meta_alerts | `./scripts/apply_pg_ddl_v4_meta_enterprise.sh` |
| CAPI pilot code | `ptt_meta/capi_dispatch.py`, `tests/test_capi_dispatch.py` |
| Nest lead write path | PG `crm_leads` + patch status API |
| Launch QA PG | `launch_qa_runs.checklist` JSONB |

### 3.2. Không block B9 UI (có thể stub)

- B11 `meta_pixels` multi-pixel → B9 dùng `client_channel_accounts.meta.pixel_id`
- B15 ads-ops wizard → B9 ship `MetaPreflightChecklist` standalone trước

---

## 4. B9 Backend — DDL & schema (~2 ngày)

### B9-BE-1 · DDL v5

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B9-BE-1a | `docs/specs/2026-07-24-postgresql-ddl-v5-meta-conversion.sql` | **CREATE** | `meta_conversion_rules` (spec §7.2) |
| B9-BE-1b | `scripts/apply_pg_ddl_v5_meta_conversion.sh` | **CREATE** | Idempotent apply + verify |
| B9-BE-1c | `ptt_crm/pg_schema.py` | **MODIFY** | `pg_meta_conversion_rules_ready()`, `apply_ddl_v5_meta_conversion()` |
| B9-BE-1d | `deploy/env.meta-enterprise-b9.example` | **CREATE** | CAPI + conversion flags |

**DDL `meta_conversion_rules` (copy spec):**

```sql
CREATE TABLE IF NOT EXISTS meta_conversion_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID REFERENCES clients (id) ON DELETE CASCADE,
    lead_status     VARCHAR(64) NOT NULL,
    event_name      VARCHAR(64) NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    require_meta_attribution BOOLEAN NOT NULL DEFAULT TRUE,
    value_vnd       BIGINT NOT NULL DEFAULT 0,
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT meta_conversion_rules_uniq
        UNIQUE (COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid), lead_status, event_name)
);
```

**Seed mặc định (migration SQL hoặc Python seed):**

| client_id | lead_status | event_name | enabled | notes |
|-----------|-------------|------------|---------|-------|
| NULL (global) | `qualified` | `CompleteRegistration` | true | default agency rule |
| NULL (global) | `post_sale` | `Purchase` | true | value from deal meta |
| NULL (global) | `new` | `Lead` | false | webhook-only |

**Acceptance:** `pg_meta_conversion_rules_ready()` → true sau apply script.

---

## 5. B9 Python — Conversion engine (~5–7 ngày)

### B9-PY-1 · `ptt_meta/conversion_rules.py` (NEW)

| # | Function | Mô tả |
|---|----------|--------|
| B9-PY-1a | `load_rules(client_id)` | Global + client override merge |
| B9-PY-1b | `evaluate_conversion_rules(lead, old_status, new_status)` | Return list dispatch intents |
| B9-PY-1c | `build_conversion_event(lead, rule)` | Map event_name, event_id convention §7.3 |
| B9-PY-1d | `require_meta_attribution_ok(lead)` | Check utm / external_campaign_id / hub map |

**`event_id` convention (giữ spec):**

| Nguồn | Pattern |
|-------|---------|
| FB Lead webhook | `leadgen_{facebook_leadgen_id}` |
| CRM qualified | `crm_qualify_{lead_id}_{status_entered_at}` |
| CRM post_sale | `crm_purchase_{lead_id}_{deal_id_or_ts}` |
| Manual retry | `manual_{lead_id}_{uuid}` |

### B9-PY-2 · Extend `ptt_meta/capi_dispatch.py`

| # | Task | Chi tiết |
|---|------|----------|
| B9-PY-2a | `dispatch_conversion_capi(...)` | Generic event builder (not only Lead) |
| B9-PY-2b | Align Lead `event_id` | Migrate `ptt-lead-*` → `leadgen_*` when external_lead_id present (backward compat read) |
| B9-PY-2c | `flush_pending_capi(client_id?, limit)` | Drain pending/failed for retry job |
| B9-PY-2d | Extend `capi_stats(hours=168)` | 7d window for tracking health |

### B9-PY-3 · `ptt_meta/conversion_sync.py` (NEW)

| # | Task | Chi tiết |
|---|------|----------|
| B9-PY-3a | `run_conversion_sync(client_id?, lookback_hours=72)` | Scan status transitions / assignment log |
| B9-PY-3b | Idempotent enqueue per `(lead_id, event_name, event_id)` | Dedup via `capi_event_log` |
| B9-PY-3c | `ptt_jobs/handlers/meta_conversion_sync.py` | Job handler |
| B9-PY-3d | `ptt_worker/__main__.py` | Register `meta_conversion_sync` |

**Cron:** hourly timer `ptt-meta-conversion-sync.timer` (staging template).

### B9-PY-4 · `ptt_meta/tracking_health.py` (NEW)

| # | Output field | Nguồn |
|---|--------------|-------|
| B9-PY-4a | `sent_7d`, `failed_7d`, `skipped_7d` | `capi_event_log` aggregate |
| B9-PY-4b | `fail_rate_pct` | failed / (sent+failed) |
| B9-PY-4c | `match_hint_pct` | sent with `em` or `ph` in payload hash proxy |
| B9-PY-4d | `avg_latency_ms` | `sent_at - created_at` |
| B9-PY-4e | `accounts[]` | pixel_id, page_id, capi_enabled, last_sent_at |

### B9-PY-5 · `ptt_meta/insights_archive.py` (NEW)

| # | Task | Chi tiết |
|---|------|----------|
| B9-PY-5a | `archive_daily_performance(dry_run=True)` | Rows older than `PTT_META_INSIGHTS_RETENTION_DAYS` (400) |
| B9-PY-5b | Optional gzip to artifact path | `.local-dev/archive/` staging |
| B9-PY-5c | Job handler + weekly timer | Log counts only in B9 (no S3 required) |

### B9-PY-6 · Tests

| File | Coverage |
|------|----------|
| `tests/test_conversion_rules.py` | Rule merge, evaluate, attribution gate |
| `tests/test_conversion_sync.py` | Backfill idempotency (mock PG) |
| `tests/test_tracking_health.py` | Stats aggregation |
| `tests/test_capi_dispatch.py` | **MODIFY** — conversion event + event_id |
| `tests/test_meta_alerts.py` | **MODIFY** — capi_fail_rate, pixel_missing, capi_stale |

---

## 6. B9 Nest — meta-tracking API (~5–7 ngày)

### B9-N-1 · Module layout

```
services/ptt-crm-api/src/meta-tracking/
├── meta-tracking.module.ts
├── meta-tracking.controller.ts
├── meta-tracking.service.ts
├── meta-tracking.repository.ts
├── meta-conversion-rules.service.ts
├── meta-conversion-rules.controller.ts
├── meta-capi-events.service.ts
├── meta-pixel-test.service.ts
├── guards/staff-meta-tracking.guard.ts
└── dto/
    ├── tracking-health.dto.ts
    ├── capi-events-query.dto.ts
    └── conversion-rule.dto.ts
```

Wire in `app.module.ts`. Cap: `meta.tracking_view` (read), `meta.tracking_configure` (rules CRUD, retry, test-pixel).

### B9-N-2 · API contract (spec §10.3)

| Method | Path | Implementation notes |
|--------|------|----------------------|
| GET | `/api/v1/meta/tracking/health` | Wrap `tracking_health.py` or inline SQL mirror |
| GET | `/api/v1/meta/capi/events` | Paginate `capi_event_log`; filter client, status, event_name |
| POST | `/api/v1/meta/capi/events/:id/retry` | Reset failed→pending; enqueue `capi_dispatch` |
| POST | `/api/v1/meta/capi/flush` | Staff admin; call Python flush or inline |
| GET | `/api/v1/meta/conversion-rules` | List global + client rules |
| POST | `/api/v1/meta/conversion-rules` | Create (configure cap) |
| PATCH | `/api/v1/meta/conversion-rules/:id` | Update enabled/value_vnd |
| POST | `/api/v1/clients/:id/channel-accounts/:accId/test-pixel` | Graph `/{pixel_id}/events` test event + test_event_code |

**Response shape `TrackingHealthResponse`:**

```typescript
{
  ok: true;
  window_days: 7;
  global: { sent: number; failed: number; skipped: number; fail_rate_pct: number; match_hint_pct: number; avg_latency_ms: number };
  accounts: Array<{
    client_id: string;
    channel_account_id: string;
    pixel_id: string | null;
    page_id: string | null;
    capi_enabled: boolean;
    last_sent_at: string | null;
    pixel_test_ok: boolean | null;
  }>;
  attribution_model: 'last_touch_crm';
}
```

### B9-N-3 · Lead status hook

| # | File | Hook |
|---|------|------|
| B9-N-3a | `services/ptt-crm-api/src/leads/leads.service.ts` (or funnel patch) | On status change → enqueue job `meta_conversion_eval` |
| B9-N-3b | `ptt_jobs/handlers/meta_conversion_eval.py` | Thin wrapper → `evaluate_conversion_rules` + dispatch |

**Không block HTTP:** enqueue async giống pattern CAPI lead hiện tại.

### B9-N-4 · Nest tests

| File | Scenarios |
|------|-----------|
| `src/meta-tracking/meta-tracking.service.spec.ts` | Health aggregation |
| `src/meta-tracking/meta-pixel-test.service.spec.ts` | Stub Graph |
| `test/meta-tracking-b9.e2e-spec.ts` | Health + events list + rules CRUD (PG seed) |
| `test/pg-contract-seed.ts` | **MODIFY** — seed capi_event_log rows + conversion rules |

---

## 7. B9 Launch QA Meta gate (~2–3 ngày)

### B9-LQ-1 · Checklist items (extend `launch_qa_runs.checklist`)

| item_key | Label (VI) | Pass condition |
|----------|------------|----------------|
| `meta_pixel_configured` | Pixel ID đã cấu hình | `client_channel_accounts.meta.pixel_id` present |
| `meta_capi_test_ok` | CAPI test event OK | Last test-pixel within 7d or inline run |
| `meta_hub_map_coverage` | Hub map ≥80% spend | reuse B8 unmapped_spend_pct ≤20% |
| `meta_capi_recent_sent` | CAPI sent trong 48h | optional strict mode flag |

### B9-LQ-2 · Services

| # | File | Hành động |
|---|------|-----------|
| B9-LQ-2a | `services/ptt-crm-api/src/meta-tracking/launch-qa-meta.util.ts` | **CREATE** | Evaluate checklist from PG |
| B9-LQ-2b | `services/ptt-crm-api/src/launch-qa/launch-qa-meta-bridge.service.ts` | **CREATE** | Sync checklist on run start / tick |
| B9-LQ-2c | `lifecycle-launch-qa.service.ts` | **MODIFY** | Block `launch_ready` if meta items fail |
| B9-LQ-2d | `ServiceDeliveryWorkflowPanel.tsx` | **MODIFY** | Show meta checklist lines |

### B9-LQ-3 · Preflight reuse (B15)

| # | File | Hành động |
|---|------|-----------|
| B9-LQ-3a | `components/meta/MetaPreflightChecklist.tsx` | **CREATE** | Props: `items: PreflightItem[]`, read-only + refresh |
| B9-LQ-3b | Used in `/meta/tracking` | Account row "Run preflight" |
| B9-LQ-3c | B15 ads-ops wizard step 4 | Import same component (future) |

---

## 8. B9 ops-web — `/meta/tracking` UI (~4–5 ngày)

### B9-FE-1 · Route & shell

| # | File | Hành động |
|---|------|-----------|
| B9-FE-1a | `app/meta/tracking/page.tsx` | **CREATE** |
| B9-FE-1b | `app/meta/tracking/MetaTrackingContent.tsx` | **CREATE** | Compose sections §7.3 UI spec |
| B9-FE-1c | `components/meta/MetaPageShell.tsx` | **REUSE** | Same header pattern as facebook-ads |
| B9-FE-1d | `components/OpsNav.tsx` | **MODIFY** | Link "Meta Tracking" under Meta group |

### B9-FE-2 · Components

| Component | Responsibility |
|-----------|----------------|
| `MetaTrackingKpiGrid.tsx` | sent / failed / skipped 7d, fail rate, match hint, avg latency |
| `MetaTrackingAccountTable.tsx` | pixel_id, page, capi_enabled, `[Test pixel]` button |
| `MetaConversionRulesTable.tsx` | CRUD table (configure cap only) |
| `MetaCapiEventsTable.tsx` | Paginated log + `[Retry]` on failed |
| `MetaPreflightChecklist.tsx` | Launch QA items per client (link to `/crm/launch-qa`) |

### B9-FE-3 · Hooks & API

| # | File | Functions |
|---|------|-----------|
| B9-FE-3a | `lib/meta/api.ts` | `fetchMetaTrackingHealth`, `fetchMetaCapiEvents`, `postMetaCapiRetry`, `postMetaTestPixel`, CRUD rules |
| B9-FE-3b | `lib/meta/types.ts` | `TrackingHealthResponse`, `CapiEventRow`, `ConversionRule` |
| B9-FE-3c | `hooks/meta/useMetaTracking.ts` | Load health + client filter |
| B9-FE-3d | `hooks/meta/useMetaCapiEvents.ts` | Pagination + retry |
| B9-FE-3e | `hooks/meta/useMetaConversionRules.ts` | List + save |
| B9-FE-3f | `lib/meta/flags.ts` | `metaTrackingEnabled()` → `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED` |

### B9-FE-4 · Hub integration (light)

| # | Task | Chi tiết |
|---|------|----------|
| B9-FE-4a | `MetaBadge` on hub client row | `CAPI OK` / `Thiếu pixel` from health snapshot |
| B9-FE-4b | Optional hub tab "Tracking" | **Defer** — link to `/meta/tracking?client_id=` first |
| B9-FE-4c | `globals.css` | `.meta-tracking-*`, test result inline styles |

**Portal-web:** **OUT of scope B9** (read-only performance only).

---

## 9. B9 Alerts extend (~1–2 ngày)

Extend `ptt_meta/alerts.py` + `meta_alerts_eval` job:

| alert_type | Condition | Dedupe key suffix |
|------------|-----------|-------------------|
| `capi_fail_rate` | failed/(sent+failed) > 10% rolling 24h | `{client_id}:{date}` |
| `pixel_missing` | account active, CAPI enabled flag, no pixel_id | `{client_id}:pixel` |
| `capi_stale` | no sent 48h AND new leads >0 in window | `{client_id}:stale` |

Nest `meta-alerts` API: no change (generic list). UI: show in Alerts tab with filter chip "Tracking".

---

## 10. B9 Gates, tests & deploy (~2–3 ngày)

### B9-QA-1 · Gate scripts

| # | File | Checks |
|---|------|--------|
| B9-QA-1a | `ptt_crm/wave_b9_gates.py` | B9-G01 module files · G02 DDL v5 · G03 conversion_rules tests · G04 capi extend tests · G05 Nest build · G06 Nest jest/e2e B9 · G07 ops-web build · G08 portal regression (no change) · G09 wave_b8 regression · G10 horizon1 meta pytest · G11 Playwright E2E-M4 (optional skip) |
| B9-QA-1b | `scripts/wave_b9_gate.sh` | Env: `WAVE_B9_SKIP_PG`, `WAVE_B9_SKIP_E2E=1` default, `WAVE_B9_SKIP_B8_GATE` |
| B9-QA-1c | `scripts/wave_b9_smoke.sh` | curl health + test-pixel stub + conversion-rules list |
| B9-QA-1d | `tests/test_b9_tracking_qa.py` | Static contract tests (mirror B8 portal QA pattern) |

### B9-QA-2 · Playwright

| ID | File | Scenario |
|----|------|----------|
| E2E-M4 | `services/ops-web/e2e/meta-tracking.spec.ts` | Login → `/meta/tracking` → KPI visible → Test pixel → inline OK |
| E2E-M4b | same | Conversion rules table loads (read-only viewer) |
| | `scripts/playwright_ops_meta_tracking_e2e.sh` | Wrapper |

### B9-QA-3 · Deploy

| Step | Command / action |
|------|------------------|
| DDL v5 staging | `./scripts/apply_pg_ddl_v5_meta_conversion.sh` |
| Rebuild | Nest + ops-web |
| Pilot env | `PTT_CAPI_ENABLED=1`, `PTT_CAPI_PILOT_CLIENTS=<uuid>`, `PTT_META_TRACKING_ENABLED=1` |
| Soak | 30d monitor `capi_event_log`, fail rate, Launch QA block rate |
| Widen | Clear pilot allowlist gradually; enable conversion sync cron |

---

## 11. Ma trận phụ thuộc file

```text
DDL v5 meta_conversion_rules
  └── conversion_rules.py ──► meta_conversion_eval job
  └── conversion_sync.py ──► hourly backfill
  └── capi_dispatch.py (extend) ──► capi_event_log
        └── meta-tracking.repository (Nest read/retry)
              └── MetaTrackingContent.tsx
                    ├── MetaTrackingKpiGrid
                    ├── MetaTrackingAccountTable ──► test-pixel API
                    ├── MetaConversionRulesTable
                    └── MetaCapiEventsTable

tracking_health.py ──► GET /meta/tracking/health ──► MetaTrackingKpiGrid
launch-qa-meta.util ──► MetaPreflightChecklist ──► B15 wizard (future)

insights_archive.py ──► weekly job (ops log only B9)
alerts.py extend ──► meta_alerts_eval ──► MetaAlertsTable (existing B8)
```

**Critical path:** `B9-BE-1 DDL` → `B9-PY-1 rules` → `B9-N-2 API` → `B9-FE-1 tracking page` → `B9-LQ-1 launch gate` → `B9-QA`.

---

## 12. Feature flags & env

| Flag | Default B9 | UI / behavior |
|------|------------|---------------|
| `PTT_CAPI_ENABLED` | `0` | Master CAPI dispatch |
| `PTT_CAPI_STUB` | `0` | Stub Graph (dev/test) |
| `PTT_CAPI_PILOT_CLIENTS` | empty | Allowlist until soak done |
| `PTT_CAPI_TEST_EVENT_CODE` | empty | Test pixel button |
| `PTT_META_TRACKING_ENABLED` | `0` | Nest guards + ops nav |
| `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED` | `0` | Hide `/meta/tracking` |
| `PTT_META_CONVERSION_SYNC_ENABLED` | `0` | Hourly backfill job |
| `PTT_META_INSIGHTS_RETENTION_DAYS` | `400` | Archive threshold |
| `PTT_LAUNCH_QA_META_STRICT` | `0` | Require capi_recent_sent for launch_ready |

**Env template:** `deploy/env.meta-enterprise-b9.example`

---

## 13. Pilot rollout & soak

### Phase 1 — Dev/staging (tuần 4)

1. Apply DDL v5 + seed default rules  
2. `PTT_CAPI_STUB=1` → verify UI + event log  
3. E2E-M4 Playwright pass  

### Phase 2 — Pilot client (tuần 5 → +30d)

1. 1 client real pixel + token vault  
2. `PTT_CAPI_ENABLED=1` + pilot UUID  
3. Monitor: fail rate <5%, match hint >70%, Launch QA pass rate  
4. Daily check `wave_b9_smoke.sh` in cron  

### Phase 3 — Widen

1. Remove pilot allowlist  
2. Enable `PTT_META_CONVERSION_SYNC_ENABLED=1`  
3. Enable tracking nav for all staff with cap  
4. **Then** start B10 intelligence (spec khuyến nghị)

---

## 14. Checklist sprint (copy sang board)

### Sprint E — B9 Backend foundation

```
[ ] B9-BE-1  DDL v5 + apply script + pg_schema + env.example
[ ] B9-PY-1  conversion_rules.py + tests
[ ] B9-PY-2  capi_dispatch extend (conversion events + event_id)
[ ] B9-N-1   Nest meta-tracking module (health, events list)
[ ] B9-N-2   test-pixel endpoint (stub + real)
[ ] PR: "meta B9 conversion DDL + tracking API skeleton"
```

### Sprint F — B9 Conversion pipeline

```
[ ] B9-PY-3  conversion_sync.py + job + worker
[ ] B9-PY-4  tracking_health.py + tests
[ ] B9-PY-5  insights_archive.py + weekly job
[ ] B9-N-3   conversion-rules CRUD + capi retry/flush
[ ] B9-N-4   Lead status hook → meta_conversion_eval
[ ] B9-PY-6  alerts extend (capi_fail_rate, pixel_missing, capi_stale)
[ ] PR: "meta B9 conversion pipeline + jobs"
```

### Sprint G — B9 UI + Launch QA

```
[ ] B9-FE-1  /meta/tracking route + MetaTrackingContent
[ ] B9-FE-2  KPI + account + rules + events tables
[ ] B9-FE-3  lib/meta/api hooks + flags
[ ] B9-LQ-1  Launch QA meta checklist + launch_ready gate
[ ] B9-FE-4  MetaPreflightChecklist + hub CAPI badge
[ ] B9-FE-5  OpsNav link + caps
[ ] PR: "meta B9 tracking UI + launch QA gate"
```

### Sprint H — B9 QA & pilot

```
[ ] B9-QA-1  wave_b9_gates.py + wave_b9_gate.sh + smoke
[ ] B9-QA-2  meta-tracking.spec.ts E2E-M4
[ ] B9-QA-3  test_b9_tracking_qa.py static checks
[ ] B9-QA-4  Staging pilot 1 client + 30d soak plan
[ ] B9-QA-5  wave_b8 + horizon1 regression
[ ] PR: "meta B9 QA gates + pilot signoff"
```

---

## Phụ lục A — Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| CAPI match rate thấp | `require_meta_attribution`; Launch QA pixel gate; hash email+phone |
| Duplicate events | DB unique `(client_id, event_id, event_name)` + idempotent jobs |
| Lead status hook miss | Hourly `meta_conversion_sync` 72h backfill |
| Graph rate limit on test-pixel | Cache last result 15m; debounce button |
| Scope creep B11 multi-pixel | B9 single pixel from channel account meta only |

---

## Phụ lục B — Out of scope B9

- B10 ROAS / anomalies UI (`/meta/intelligence`)
- B11 `meta_pixels` multi-pixel CRUD
- B15 ads-ops wizard (chỉ ship `MetaPreflightChecklist` component)
- Portal tracking page (client không test pixel)
- ClickHouse / warehouse (B14)

---

*Tài liệu này là plan thực thi B9; cập nhật version khi DDL/API thay đổi trong implement.*
