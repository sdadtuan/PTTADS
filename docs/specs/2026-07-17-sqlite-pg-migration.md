# SQLite → PostgreSQL Migration Matrix (Phase 1)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-17  
> **Chiến lược Phase 1:** Dual database — CRM OLTP vẫn **SQLite**; PostgreSQL chỉ domain agency mới.

---

## 1. Tổng quan

| Database | Phase 1 role | Cutover |
|----------|--------------|---------|
| **SQLite** (`data/*.db`) | CRM leads, hub, SOP, staff, RE | Primary — không đổi |
| **PostgreSQL** (`ptt_agency`) | clients, job_queue, events, notifications | Primary — mới |

**Bridge fields (không FK cross-DB):**

- `crm_leads.meta_json.agency_client_id` — UUID hoặc client `code`
- `crm_hub_campaigns` — column/meta `meta_campaign_id` (SQLite migration nhỏ, Phase 1 UI)

---

## 2. Bảng PostgreSQL mới (không migrate từ SQLite)

| PG table | Nguồn logic cũ | Ghi chú |
|----------|----------------|---------|
| `clients` | `crm_customers` (một phần) | **Tách:** agency client ≠ end customer |
| `client_onboarding_items` | — | Mới |
| `client_channel_accounts` | FB config rải rác env/DB | Centralize |
| `job_queue` | — | Mới |
| `domain_events` | — | Outbox |
| `notification_inbox` | Hub reminders (partial) | Mới unified |
| `kpi_definitions` | Hardcoded KPI rules | Seed DDL |
| `crm_leads` | `crm_lead_store.py` (SQLite) | **Read replica** — DDL v2, sync Bước 6 |
| `crm_leads_sync_state` | — | Sync watermark |

---

## 3. SQLite giữ nguyên Phase 1

| SQLite table | Module | Migrate PG |
|--------------|--------|------------|
| `crm_leads` | `crm_lead_store.py` | Phase 1b ✅ DDL v2 (read replica; sync Bước 6) |
| `crm_customers` | CRM | Phase 1b (end customer) |
| `crm_cases` | CSKH | Phase 2 |
| `crm_sales_hub_*` | Hub | Phase 2 |
| `crm_sop_*` | SOP | Phase 2 |
| `crm_staff` | HR | Phase 2 |
| `crm_re_projects` | RE | Phase 3 |
| `crm_kpi_*` | KPI | Phase 2 |
| `seo_*` (PTTADS) | SEO/AEO Ops | **Phase 3.5** — freeze SQLite 2026-07-19 |
| CMS tables | CMS | Phase 4 |

---

## 4. Mapping tham chiếu (future)

| SQLite | PostgreSQL target | Transform |
|--------|-------------------|-----------|
| `crm_customers.id` | `customers.id` (future) | Giữ end-customer |
| `crm_customers.company_name` | `clients.name` | Chỉ khi là agency client — manual map |
| `crm_leads.meta` → `facebook_leadgen_id` | `job_queue.payload` | Qua ingest job |
| `crm_leads.utm_campaign` | `daily_performance` (Phase 2) | — |

---

## 5. Lead ingest bridge (Phase 1)

```
Webhook v1 → job_queue (PG)
  → worker → ingest_webhook_leads (SQLite)
  → meta.agency_client_id = X-PTT-Client-Id
  → domain_events LeadCreated (PG)
```

Không duplicate lead row vào PG Phase 1.

**Phase 1b Bước 6** — sau ingest, `ptt_crm.lead_sync` upsert vào `crm_leads` (PG read replica):

```
ingest_lead success → sync_after_ingest(created_ids) → PG crm_leads
Cron: POST /api/crm/agency/lead-sync-cron?mode=incremental|full|reconcile
```

---

## 6. Thứ tự migrate Phase 1b+

| Order | Domain | Risk |
|-------|--------|------|
| 1 | `clients` manual seed từ Hub HĐ | Low |
| 2 | `crm_leads` read replica PG | Medium |
| **3** | `crm_leads` write dual-run → PG OLTP primary | High | [`2026-07-17-postgresql-ddl-v3-leads-oltp.sql`](2026-07-17-postgresql-ddl-v3-leads-oltp.sql) |
| **3b** | `daily_performance` + closed-loop | Medium | [`2026-07-17-postgresql-ddl-v3-performance.sql`](2026-07-17-postgresql-ddl-v3-performance.sql) |
| **3.5** | **SEO/AEO domain** (`seo_aeo.*`) | Medium | [`2026-07-19-seo-aeo-pg-cutover-policy.md`](2026-07-19-seo-aeo-pg-cutover-policy.md) — **no new SQLite SEO schema** |
| 4 | Hub, SOP | Medium |
| 5 | Staff, KPI | Medium |
| 6 | CMS | Low |

---

## 7. Rollback

- Tắt `PTT_WEBHOOK_V1_ENQUEUE=0` → legacy webhook inline.
- Worker stop → jobs accumulate; replay sau.
- Drop PG schema không ảnh hưởng SQLite CRM.

---

## 8. Verification checklist

- [ ] PG DDL v1 applied; `\dt` shows agency tables
- [ ] PG DDL v2 applied; `\d crm_leads` read replica
- [ ] PG DDL v3 applied; OLTP columns + `daily_performance` (Phase 2)
- [ ] Worker processes job; lead appears in SQLite
- [ ] `domain_events` row on LeadCreated
- [ ] CRM regression L01–L26 pass
- [ ] No SQLite schema change required for minimal path
