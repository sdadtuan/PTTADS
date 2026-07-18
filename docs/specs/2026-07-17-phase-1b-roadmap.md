# Phase 1b Roadmap — NestJS Read API + PG Lead Migration

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-17  
> **Phạm vi:** Evolution sau PRD Phase 1 — NestJS CRM read, dual-run, bắt đầu migrate `crm_leads` sang PostgreSQL  
> **PRD Phase 1:** [`2026-07-17-prd-phase-1.md`](2026-07-17-prd-phase-1.md)  
> **Architecture Phase 1:** [`2026-07-17-architecture-phase-1.md`](2026-07-17-architecture-phase-1.md)  
> **Migration matrix:** [`2026-07-17-sqlite-pg-migration.md`](2026-07-17-sqlite-pg-migration.md)  
> **Master spec:** [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md)  
> **Event catalog:** [`events/catalog.yaml`](events/catalog.yaml)

---

## Mục lục

1. [Tóm tắt](#1-tóm-tắt)
2. [Điều kiện tiên quyết (Phase 1 gate)](#2-điều-kiện-tiên-quyết-phase-1-gate)
3. [Trạng thái hiện tại](#3-trạng-thái-hiện-tại)
4. [Thứ tự các bước Phase 1b](#4-thứ-tự-các-bước-phase-1b)
5. [Sơ đồ phụ thuộc](#5-sơ-đồ-phụ-thuộc)
6. [Definition of Done — Phase 1b](#6-definition-of-done--phase-1b)
7. [API contract v1 (freeze)](#7-api-contract-v1-freeze)
8. [Feature flags & env](#8-feature-flags--env)
9. [Out of scope Phase 1b](#9-out-of-scope-phase-1b)
10. [Ước lượng thời gian](#10-ước-lượng-thời-gian)
11. [Rollback](#11-rollback)
12. [Liên kết implementation hiện có](#12-liên-kết-implementation-hiện-có)

---

## 1. Tóm tắt

Phase 1b là giai đoạn **Strangler Fig tiếp theo** sau PRD Phase 1 (Flask + worker + PG sidecar). Mục tiêu:

- **NestJS** phục vụ **Lead read API** (`/api/v1/leads`) với response **diff 0%** so với Flask.
- **PostgreSQL** bắt đầu có bảng `crm_leads` dạng **read replica** (sync từ SQLite).
- **RabbitMQ** publish domain events từ outbox PG (`ptt.events`) trên staging/production.
- **Không** cutover CRM write prod trong Phase 1b — Flask + SQLite vẫn OLTP primary cho assign/update.

**North-star metric Phase 1b:** Dual-run read Flask/Nest diff 0% trên staging ≥ 7 ngày; read traffic prod qua Nest có rollback trong ≤ 5 phút.

**ADR liên quan:** ADR-002 (defer NestJS đến sau queue stable), ADR-001 (dual DB), migration matrix order #2–#3.

---

## 2. Điều kiện tiên quyết (Phase 1 gate)

Không bắt đầu Phase 1b cho đến khi **Bước 0** pass trên **staging** (không chỉ local dev).

| # | Gate | Verification |
|---|------|--------------|
| G1 | 100% webhook lead qua queue idempotent | Meta + Zalo fixture + replay cùng `external_lead_id` → 1 lead |
| G2 | DLQ replay hoạt động | Job `dead` → `POST /api/v1/jobs/{id}/replay` → `done` |
| G3 | Form ingest không silent fail | Lỗi DB → job failed + log; sync fallback documented |
| G4 | Worker + SLA cron systemd | Runbook [`local-phase1-dev.md`](../runbooks/local-phase1-dev.md) áp dụng VPS |
| G5 | Regression CRM L01–L26 | QA sign-off trên staging |
| G6 | Sentry UAT | Exception webhook/worker có `correlation_id` tag |
| G7 | Client onboarding checklist | `PTT_CLIENT_STRICT_ONBOARDING` tested trên staging |

**Exit Bước 0:** Checklist G1–G7 signed; không blocker P0 mở trên production ingest.

---

## 3. Trạng thái hiện tại

Cập nhật sau implementation Phase 1 (2026-07-17):

| Hạng mục | Trạng thái | Ghi chú |
|----------|------------|---------|
| Webhook v1 → queue → worker → SQLite | ✅ Done | `blueprints/channel_webhooks.py`, `ptt_worker` |
| Client registry + Agency Ops UI | ✅ Done | `blueprints/agency.py`, `SPEC_UI_UX_AGENCY.md` |
| Flask `/api/v1/leads` read | ✅ Done | `ptt_crm/leads_read.py`, `blueprints/crm_leads_v1.py` |
| OpenAPI + contract tests (Bước 2) | ✅ Done | `schemas/crm/leads-v1.openapi.yaml`, `tests/test_leads_v1_contract.py` |
| NestJS read API (Bước 3) | ✅ Done | `services/ptt-crm-api/` |
| Dual-run Flask/Nest (Bước 4) | ✅ Done | `ptt_crm/dual_run.py`, `scripts/dual_run_leads_check.py` |
| PG `crm_leads` DDL v2 (Bước 5) | ✅ Done | `2026-07-17-postgresql-ddl-v2-leads.sql` |
| Lead replica sync (Bước 6) | ✅ Done | `ptt_crm/lead_sync.py`, `sync_lead_replica` job |
| Domain events outbox PG | ✅ Done | `ptt_jobs/events.py`, `domain_events` table |
| RMQ broker + publisher | ✅ Code | `ptt_jobs/broker.py`; mặc định `PTT_EVENT_PUBLISH_RMQ=0` |
| `/api/v1/events` + ingest UI panel | ✅ Done | Pipeline ingest monitor |
| Nest read PG (Bước 7) | ✅ Done | `PgLeadsRepository`, `PTT_LEADS_READ_SOURCE=pg` |
| Read traffic cutover (Bước 8) | ✅ Done | Nginx + `PTT_LEADS_READ_UPSTREAM`, runbook B8 |
| Write staging POC (Bước 9) | ✅ Done | `PTT_LEADS_WRITE_ENABLED`, OpenAPI write draft |

---

## 4. Thứ tự các bước Phase 1b

Làm **tuần tự** theo số bước. Bước 1 và 2 có thể song song sau Bước 0.

### Bước 0 — Gate Phase 1 (staging UAT)

**Mục tiêu:** Pipeline ingest ổn định trước khi thêm NestJS / dual-run.

**Tasks:**

1. Deploy staging VPS mirror prod (Flask + worker + PG + RMQ).
2. Chạy `./scripts/local_phase1_smoke.sh` trên staging; mở rộng manual webhook test.
3. QA regression **L01–L26** + Agency Ops flows (A-01–A-09).
4. Sign-off checklist §2 (G1–G7).

**Deliverables:** UAT report; Sentry project staging; runbook worker systemd.

**Exit criteria:** G1–G7 pass; DLQ count = 0 sau 24h soak (hoặc có runbook xử lý).

---

### Bước 1 — Event infrastructure (RMQ prod/staging)

**Phụ thuộc:** Bước 0  
**Risk:** Thấp

**Tasks:**

1. Cài `pika` trên worker VPS; set `PTT_EVENT_PUBLISH_RMQ=1`, `RABBITMQ_URL`.
2. Khai báo exchange `ptt.events` (topic) và queue subscriber stub (observability / log consumer).
3. Verify pipeline: ingest lead → `LeadCreated` trong `domain_events` → RMQ → `published_at` set.
4. Alert: `COUNT(*) WHERE published_at IS NULL` > threshold trong 5 phút.

**Deliverables:** RMQ topology doc; Grafana/SQL alert query (hoặc cron check).

**Exit criteria:** 100% events test trên staging publish trong ≤ 30s; không event stuck > 1h.

---

### Bước 2 — API contract v1 freeze

**Phụ thuộc:** Bước 0  
**Risk:** Thấp  
**Song song với:** Bước 1

**Tasks:**

1. Freeze DTO lead v1 (xem [§7](#7-api-contract-v1-freeze)).
2. Viết OpenAPI `schemas/crm/leads-v1.openapi.yaml`.
3. Golden JSON fixtures từ Flask (`tests/fixtures/api/leads-v1/`).
4. Contract test: response Flask = golden file (CI).
5. Chốt auth Phase 1b: Flask session proxy **hoặc** internal header `X-PTT-Internal-Key` (chưa JWT).

**Deliverables:** OpenAPI spec; contract tests trong CI.

**Exit criteria:** Mọi thay đổi DTO qua PR + version bump; CI contract test green.

---

### Bước 3 — NestJS scaffold (read-only)

**Phụ thuộc:** Bước 2  
**Risk:** Trung bình  
**Strangler order:** #3 Lead read API

**Tasks:**

1. Tạo `services/ptt-crm-api/` — NestJS modular monolith.
2. Modules: `LeadsModule`, `HealthModule`, `ConfigModule`.
3. Phase 1b đầu: repository đọc **SQLite read-only** (cùng path `PTT_SQLITE_PATH`).
4. Implement:
   - `GET /api/v1/leads` — filters + pagination
   - `GET /api/v1/leads/:id`
   - `GET /health`
5. Docker Compose service `crm-api` (:3000); document Nginx routing.

**Deliverables:** NestJS repo folder; Dockerfile; compose override.

**Exit criteria:** Nest trả JSON khớp golden fixtures; health OK; không write endpoint.

---

### Bước 4 — Dual-run read (Flask vs Nest)

**Phụ thuộc:** Bước 3 (+ Bước 1 khuyến nghị xong)  
**Risk:** Trung bình

**Tasks:**

1. Feature flag `PTT_LEADS_API_DUAL_RUN=1`: middleware so sánh Flask vs Nest (staging).
2. Script `scripts/dual_run_leads_check.py`: sample N leads → diff report.
3. Sentry tag `dual_run_mismatch` khi field lệch.
4. Soak test staging ≥ 7 ngày.

**Deliverables:** Dual-run script; dashboard/log query mismatch count.

**Exit criteria:** Diff 0% trên toàn bộ sample set; 0 mismatch trong 7 ngày soak.

---

### Bước 5 — PG DDL `crm_leads` read replica

**Phụ thuộc:** Bước 4 pass  
**Risk:** Trung bình  
**Migration matrix:** order #2

**Tasks:**

1. DDL v2: `docs/specs/2026-07-17-postgresql-ddl-v2-leads.sql`.
2. Bảng `crm_leads` subset: id, contact fields, status, source, owner_id, meta_json JSONB, sync metadata.
3. Index: `(agency_client_id)`, `(created_at DESC)`, `(external_lead_id)` — extract từ meta hoặc generated column.
4. **Không** FK cross-DB; `agency_client_id` UUID nullable.

**Deliverables:** DDL v2 file; migration apply script staging.

**Exit criteria:** `\d crm_leads` trên staging; schema review approved; bảng rỗng OK.

---

### Bước 6 — Sync worker (SQLite → PG replica)

**Phụ thuộc:** Bước 5  
**Risk:** Trung bình

**Tasks:**

1. Job type `sync_lead_replica` hoặc dedicated poller: watermark `MAX(sqlite_id)`.
2. Trigger: sau `ingest_lead` success + cron backfill historical leads.
3. Reconcile job hàng ngày: COUNT + hash sample Flask SQLite vs PG replica.
4. Idempotency: upsert by `sqlite_lead_id` UK.

**Deliverables:** Handler `ptt_jobs/handlers/sync_lead_replica.py`; reconcile script.

**Exit criteria:** Lead mới ingest xuất hiện PG ≤ 1 phút; reconcile diff 0% staging.

---

### Bước 7 — Nest đọc PostgreSQL (thay SQLite) ✅

**Phụ thuộc:** Bước 6 ổn định  
**Risk:** Trung bình  
**Status:** Implemented (local)

**Tasks:**

1. Nest `LeadsRepository` chuyển SQLite → PG read replica (`DATABASE_URL`).
2. Dual-run mới: Flask (SQLite) vs Nest (PG replica) — diff 0%.
3. Load test read API (p95 latency baseline).

**Deliverables:**

- `PgLeadsRepository` + `SqliteLeadsRepository` facade (`PTT_LEADS_READ_SOURCE=pg|sqlite`)
- `pgRowToV1()` mirror Python `pg_row_to_v1`
- Health: `leads_read_source`, `postgres`
- docker-compose `crm-api` → PG + `depends_on: postgres`
- E2E: `test/leads-pg.e2e-spec.ts` (skips if PG unavailable)
- `./scripts/local_crm_api_up.sh` default PG mode

**Exit criteria:** Diff 0% Flask SQLite vs Nest PG trên staging ≥ 3 ngày.

**Verify locally:**

```bash
./scripts/local_phase1_up.sh docker
./scripts/sync_leads_backfill.sh
cd services/ptt-crm-api && npm install && npm test && npm run test:e2e
./scripts/local_crm_api_up.sh &
./scripts/local_dual_run_check.sh 50
```

---

### Bước 8 — Cutover read traffic (production) ✅

**Phụ thuộc:** Bước 7  
**Risk:** Trung bình–cao  
**Status:** Implemented (config + runbook; prod cutover manual)

**Tasks:**

1. Nginx: `api.pttads.vn/api/v1/leads` → NestJS upstream.
2. Flask giữ CRM UI + legacy write APIs (`/api/crm/leads`, assign, …).
3. Feature flag rollback: `PTT_LEADS_READ_UPSTREAM=nest|flask`.
4. Monitor 1 tuần: error rate, latency, Sentry.

**Deliverables:**

- `deploy/nginx-leads-v1-cutover.conf` + upstream nest/flask snippets
- `scripts/apply_leads_read_upstream.sh` — ghi snippet + reload nginx
- `deploy/ptt-crm-api.service` — systemd Nest
- `ptt_crm/leads_upstream.py` — Flask proxy sau session auth
- `docs/runbooks/cutover-leads-read-b8.md`
- `scripts/local_leads_cutover_drill.sh`

**Exit criteria:** Read prod trên Nest; rollback drill pass; không regression Agency Ops UI.

**Verify:**

```bash
./scripts/apply_leads_read_upstream.sh --dry-run
./scripts/local_leads_cutover_drill.sh
python -m unittest tests.test_leads_read_upstream -q
```

---

### Bước 9 — Write dual-run prep (staging only) ✅

**Phụ thuộc:** Bước 8 ổn  
**Risk:** Cao  
**Status:** Implemented (staging POC)

**Tasks:**

1. Spec `POST/PATCH /api/v1/leads` (create stub, assign, score stub) — OpenAPI draft.
2. Nest write → PG (staging); Flask write vẫn SQLite.
3. Event `LeadAssigned` qua outbox khi assign từ Nest staging.
4. **Không** bật write dual-run production — defer cutover đầu Phase 2.

**Deliverables:**

- `schemas/crm/leads-v1-write.openapi.yaml` + JSON schemas
- Nest `LeadsWriteService`, `PgLeadsWriteRepository`, `WriteEnabledGuard`
- `PTT_LEADS_WRITE_ENABLED=0` default (404 khi tắt)
- Staging id range ≥ 900000000
- E2E `test/leads-write.e2e-spec.ts`
- Phase 2 ticket: `docs/specs/2026-07-17-phase-2-write-cutover-ticket.md`

**Exit criteria:** Write path proven staging; Phase 2 ticket rõ cho PG write primary.

**Verify staging:**

```bash
export PTT_LEADS_WRITE_ENABLED=1
./scripts/local_crm_api_up.sh
curl -X POST http://127.0.0.1:3000/api/v1/leads -H 'Content-Type: application/json' \
  -d '{"full_name":"Staging Lead","channel":"meta"}'
curl -X PATCH http://127.0.0.1:3000/api/v1/leads/900000001 \
  -H 'Content-Type: application/json' -d '{"owner_id":42,"assigned_by":"admin"}'
cd services/ptt-crm-api && npm run test:e2e -- leads-write.e2e-spec.ts
```

---

## 5. Sơ đồ phụ thuộc

```mermaid
flowchart TD
    G0["B0 Gate Phase 1 UAT"]
    G0 --> S1["B1 RMQ events staging/prod"]
    G0 --> S2["B2 OpenAPI + contract freeze"]
    S2 --> S3["B3 NestJS scaffold read"]
    S3 --> S4["B4 Dual-run Flask vs Nest"]
    S1 --> S4
    S4 --> S5["B5 PG crm_leads DDL"]
    S5 --> S6["B6 Sync SQLite → PG"]
    S6 --> S7["B7 Nest read PG"]
    S7 --> S8["B8 Cutover read prod"]
    S8 --> S9["B9 Write dual-run staging only"]
```

**Strangler mapping (Master spec §13.3):**

| Strangler # | Phase 1b bước | Module |
|-------------|-----------------|--------|
| 1–2 | (Phase 1 done) | Webhook, Client/Tenant |
| 3 | B3–B8 | Lead read API |
| 4 | B9 (staging) | Lead write + assign |

---

## 6. Definition of Done — Phase 1b

- [ ] Bước 0 gate signed (staging UAT L01–L26)
- [ ] RMQ outbox publish 100% trên staging/prod (`PTT_EVENT_PUBLISH_RMQ=1`)
- [ ] OpenAPI leads-v1 frozen + contract tests CI
- [ ] NestJS `GET /api/v1/leads` deployed staging + prod
- [ ] Dual-run read Flask/Nest **diff 0%** ≥ 7 ngày staging
- [ ] PG `crm_leads` read replica sync ≤ 1 phút lag
- [ ] Read traffic prod qua Nest; rollback tested
- [ ] Write dual-run **staging only** — spec + POC, không prod cutover
- [ ] Runbook + Sentry dashboards cập nhật
- [ ] Master spec §13.4 item *Dual-run CRM read* checked

---

## 7. API contract v1 (freeze)

Source of truth implementation: `ptt_crm/leads_read.py` → `lead_row_to_v1()`.

### 7.1. `GET /api/v1/leads`

**Query params:**

| Param | Type | Mô tả |
|-------|------|-------|
| `client_id` | UUID | `meta.agency_client_id` |
| `status` | string | Trạng thái lead |
| `source` | string | Nguồn CRM (`facebook`, `web`, …) |
| `channel` | string | Kênh ingest (`meta`, `zalo`, …) |
| `q` | string | Tìm tên / phone / email |
| `limit` | int | Default 50, max 200 |
| `offset` | int | Default 0 |

**Response:**

```json
{
  "leads": [ { "...LeadV1" } ],
  "total": 123,
  "limit": 50,
  "offset": 0
}
```

### 7.2. LeadV1 object

| Field | Type | Mô tả |
|-------|------|-------|
| `id` | int | SQLite lead id (stable cho đến PG cutover) |
| `full_name` | string | |
| `phone` | string | |
| `email` | string | |
| `status` | string | |
| `source` | string | CRM source |
| `channel` | string | Ingest channel normalized |
| `client_id` | UUID \| null | Agency client (`agency_client_id`) |
| `campaign_id` | string \| null | |
| `external_lead_id` | string \| null | Meta/Zalo external id |
| `owner_id` | int \| null | Staff owner |
| `created_at` | string | |
| `received_at` | string | Ingest / FB created time |
| `is_duplicate` | bool | |

### 7.3. `GET /api/v1/leads/:id`

Trả single `LeadV1` hoặc `404`.

### 7.4. NestJS parity rule

Mọi field trong LeadV1 phải **byte-identical** giữa Flask và Nest trên dual-run (trừ khi documented nullable coercion). Thay đổi breaking → bump API version `v2`.

---

## 8. Feature flags & env

| Flag | Default | Bước | Mô tả |
|------|---------|------|-------|
| `PTT_EVENT_PUBLISH_RMQ` | `0` | 1 | Publish outbox → RabbitMQ |
| `RABBITMQ_URL` | — | 1 | `amqp://ptt:ptt_dev@127.0.0.1:5672/` |
| `PTT_LEADS_API_DUAL_RUN` | `0` | 4 | So sánh Flask vs Nest mỗi request |
| `PTT_NEST_LEADS_URL` | — | 4 | Base URL Nest internal |
| `PTT_LEADS_READ_UPSTREAM` | `flask` | 8 | `flask` \| `nest` — Nginx routing |
| `PTT_LEAD_REPLICA_SYNC` | `0` | 6 | Bật sync SQLite → PG |
| `PTT_SQLITE_PATH` | `ptt.db` | 3–7 | Shared SQLite path |
| `DATABASE_URL` | — | 5+ | PostgreSQL agency schema |

---

## 9. Out of scope Phase 1b

| Hạng mục | Phase defer | Lý do |
|----------|-------------|-------|
| JWT / Keycloak portal auth | Phase 2 | Flask session đủ internal ops |
| Meta Marketing API insights | Phase 2 | U-P1-01 |
| Metrics engine CPL/ROAS | Phase 2 | U-P1-02 |
| CAPI collector | Phase 2 | U-P1-03 |
| Next.js client portal | Phase 3 | ADR-005 |
| CRM write prod cutover PG | Phase 2 | Rủi ro cao; B9 staging only |
| Deprecate Flask monolith | Phase 4 | Strangler dài hạn |
| Hub / SOP migrate PG | Phase 2+ | Migration matrix order #4 |

---

## 10. Ước lượng thời gian

Giả định 1 BE full-time + QA part-time:

| Bước | Thời gian | Ghi chú |
|------|-----------|---------|
| 0 | 1–2 tuần | UAT staging |
| 1–2 | 3–5 ngày | Song song |
| 3–4 | 2–3 tuần | Nest + dual-run soak |
| 5–7 | 2–3 tuần | PG replica + sync |
| 8 | 3–5 ngày | Cutover + rollback drill |
| 9 | 2–4 tuần | Staging write POC |

**Tổng Phase 1b:** ~6–10 tuần, trước khi bắt Phase 2 (Meta closed-loop + CRM write PG).

**PRD Phase 2:** [`2026-07-17-prd-phase-2.md`](2026-07-17-prd-phase-2.md)  
**Architecture Phase 2:** [`2026-07-17-architecture-phase-2.md`](2026-07-17-architecture-phase-2.md)

---

## 11. Rollback

| Tình huống | Hành động |
|------------|-----------|
| Nest read lỗi prod | `PTT_LEADS_READ_UPSTREAM=flask`; Nginx → Flask |
| RMQ publish fail | `PTT_EVENT_PUBLISH_RMQ=0`; outbox tích lũy; replay sau |
| PG replica lệch | Tắt `PTT_LEAD_REPLICA_SYNC`; Nest đọc SQLite tạm |
| Sync worker bug | Stop handler; SQLite vẫn primary; reconcile manual |
| Toàn bộ Phase 1b | Nest service down; Flask + SQLite + PG sidecar như Phase 1 |

Drop bảng PG `crm_leads` **không** ảnh hưởng SQLite CRM OLTP.

---

## 12. Liên kết implementation hiện có

| Artifact | Path |
|----------|------|
| Lead read layer | `ptt_crm/leads_read.py` |
| Flask leads API | `blueprints/crm_leads_v1.py` |
| Events API | `GET /api/v1/events` |
| Outbox emit | `ptt_jobs/events.py` |
| RMQ broker | `ptt_jobs/broker.py` |
| Event publisher | `ptt_jobs/event_publisher.py` |
| Worker | `ptt_worker/__main__.py` |
| Contract tests | `tests/test_crm_leads_v1.py` |
| OpenAPI v1 | `schemas/crm/leads-v1.openapi.yaml` |
| JSON Schema LeadV1 | `schemas/crm/lead-v1.schema.json` |
| Golden fixtures | `tests/fixtures/api/leads-v1/` |
| Contract test suite | `tests/test_leads_v1_contract.py` |
| NestJS CRM API | `services/ptt-crm-api/` |
| Dual-run compare | `ptt_crm/dual_run.py` |
| Dual-run CLI | `scripts/dual_run_leads_check.py` |
| PG leads DDL v2 | `docs/specs/2026-07-17-postgresql-ddl-v2-leads.sql` |
| PG schema helpers | `ptt_crm/pg_schema.py` |
| Lead sync | `ptt_crm/lead_sync.py` |
| Reconcile script | `scripts/reconcile_lead_replica.sh` |
| Cutover runbook B8 | `docs/runbooks/cutover-leads-read-b8.md` |
| Nginx leads cutover | `deploy/nginx-leads-v1-cutover.conf` |
| Apply upstream script | `scripts/apply_leads_read_upstream.sh` |
| Flask upstream proxy | `ptt_crm/leads_upstream.py` |
| Smoke script | `scripts/local_phase1_smoke.sh` |
| Local runbook | `docs/runbooks/local-phase1-dev.md` |

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Initial Phase 1b roadmap |
