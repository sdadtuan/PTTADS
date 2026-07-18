# ChannelAdapter — Multi-channel Ads Platform (PTTADS)

**Ngày:** 2026-07-16  
**Trạng thái:** Phase 0 — contract + adapter stubs  
**Liên quan:** `PTT/docs/facebook_ads_agency_techservice.txt`, `schemas/channel/`  
**PRD Phase 1:** [`2026-07-17-prd-phase-1.md`](2026-07-17-prd-phase-1.md) · **Architecture:** [`2026-07-17-architecture-phase-1.md`](2026-07-17-architecture-phase-1.md) · **UI/UX:** [`../SPEC_UI_UX_AGENCY.md`](../SPEC_UI_UX_AGENCY.md)

---

## 1. Mục tiêu

Chuẩn bị migration stack agency (Meta, Zalo, Google, Email, …) bằng **một interface plugin** — CRM/Metrics core không phụ thuộc kênh cụ thể.

## 2. Cấu trúc repo

```
PTTADS/
  ptt_channel/
    base.py              # ChannelAdapter ABC
    registry.py          # ChannelAdapterRegistry
    ingress.py           # parse_channel_webhook()
    models.py            # NormalizedLead, NormalizedEvent, …
    mappers.py           # Legacy CRM rows → normalized
    adapters/
      meta.py            # ✅ wrap crm_lead_webhooks Facebook
      zalo.py            # ✅ wrap parse_zalo_webhook
      google.py          # stub Phase 2
      email.py           # stub Phase 3
  schemas/channel/       # JSON Schema + OpenAPI
  blueprints/channel_webhooks.py   # /api/v1/webhooks/{channel}
  tests/test_ptt_channel.py
```

## 3. API (Flask — đã đăng ký)

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/v1/channels` | Danh sách adapter + capabilities |
| GET/POST | `/api/v1/webhooks/{channel}` | Ingress thống nhất |

Legacy vẫn hoạt động: `/api/crm/integration/webhooks/facebook`, `/zalo`.

Header tuỳ chọn: `X-PTT-Client-Id` — gán `client_id` cho normalized lead.

## 4. Normalized models

Xem JSON Schema trong `schemas/channel/`. Mọi adapter **phải** map về:

- `NormalizedLead` — ingest CRM Sync
- `NormalizedEvent` — Tracking / dedup
- `NormalizedDailyPerformance` — Metrics engine (Phase 2)

## 5. Roadmap implement

| Phase | Nội dung |
|-------|----------|
| **0** (hiện tại) | Interface, Meta/Zalo webhook, OpenAPI, tests |
| **1** | PostgreSQL `client_channel_accounts`, job queue sync |
| **2** | Meta Marketing API insights; Google adapter |
| **3** | Email ESP; client portal read models |
| **4** | NestJS API gateway — import cùng JSON Schema |

## 6. Wiring CRM

Webhook v1 → `enqueue_ingest_leads()` → `ptt-worker` → `ingest_webhook_leads()` (Phase 1 ✅).

```python
# blueprints/channel_webhooks.py
from ptt_jobs.enqueue import enqueue_ingest_leads
enqueue_ingest_leads(leads, channel=channel, correlation_id=..., client_id=...)
```

Legacy route vẫn hoạt động song song cho đến UAT (`PTT_WEBHOOK_V1_PRIMARY` — future).

**Env:** `DATABASE_URL`, `PTT_WEBHOOK_V1_ENQUEUE=1`, `PTT_JOBS_SYNC_FALLBACK=1`

---

**Tài liệu agency gốc:** `/Users/quoctuan/Documents/CursorAI/PTT/docs/facebook_ads_agency_techservice.txt`
