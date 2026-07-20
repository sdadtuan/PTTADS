# Plan: SEO/AEO Phase 3.5 — PostgreSQL cutover (gate trước Phase 4)

> **Ngày:** 2026-07-19 · **Trạng thái:** **Implemented** (default `SEO_AEO_DB=sqlite`; set `pg` after backfill)  
> **Policy:** [`specs/2026-07-19-seo-aeo-pg-cutover-policy.md`](../../specs/2026-07-19-seo-aeo-pg-cutover-policy.md)  
> **Thời lượng ước tính:** 1–2 tuần dev + 1 tuần UAT 1 client pilot

---

## Mục tiêu

Chuyển **toàn bộ read/write SEO/AEO domain** từ SQLite (`ptt.db` tables `seo_*`) sang PostgreSQL (`seo_aeo.*`), giữ **read-only bridge** tới CRM SQLite master (`crm_customers`, `crm_service_lifecycle`).

Sau cutover: **không feature mới trên SQLite SEO** (policy active từ trước cutover code).

---

## Phạm vi

### In scope

| # | Task | Output |
|---|------|--------|
| 1 | Apply PG DDL production/staging | `deploy/sql/seo_aeo_pg_schema.sql` applied |
| 2 | `ptt_seo/db.py` | `seo_connection()`, `SEO_AEO_DB` env flag |
| 3 | Repository layer hoặc SQL adapter | `%s` placeholders, JSONB, `RETURNING id` |
| 4 | Refactor `ptt_seo/*` writes | settings, projects, initiatives, research, content, technical, gsc, alerts |
| 5 | Blueprint `seo_aeo.py` | Dual path → PG-only sau flag |
| 6 | Backfill script | `scripts/migrate_sqlite_seo_aeo_to_pg.py` (idempotent) |
| 7 | Hub/delivery reads | CRM từ SQLite; SEO metrics từ PG |
| 8 | Tests | `tests/test_seo_aeo_pg_cutover.py` + CI PG service |
| 9 | Runbook cutover | Rollback, verify, freeze SQLite tables |

### Out of scope (Phase 4)

- GSC/GA4 OAuth live API
- Migrate `crm_aeo_*` legacy tables
- Bỏ SQLite CRM master (platform-wide — xem migration matrix)

---

## Kiến trúc sau cutover

```
Flask seo_aeo blueprint
  ├── READ  CRM: sqlite3 via deps.get_connection()  [customer, lifecycle, staff]
  └── R/W   SEO:  psycopg2 via ptt_seo/db.py        [seo_aeo.*]

ptt-worker
  └── handlers/seo_*  →  PG only
```

Env:

| Variable | Values | Default |
|----------|--------|---------|
| `SEO_AEO_DB` | `pg` \| `sqlite` \| `dual` | `sqlite` (pre-cutover) → **`pg` production** |
| `DATABASE_URL` | PostgreSQL DSN | Required when `SEO_AEO_DB=pg` |

---

## Thứ tự triển khai

### Bước 1 — Infrastructure (0.5 ngày)

- [ ] Verify `DATABASE_URL` trên VPS staging + production
- [ ] `\i deploy/sql/seo_aeo_pg_schema.sql` trên `ptt_agency`
- [ ] Smoke: `SELECT 1 FROM seo_aeo.seo_client_settings LIMIT 0`

### Bước 2 — DB layer (1–2 ngày)

- [ ] Tạo `ptt_seo/db.py` wrap `ptt_jobs.db.pg_connection`
- [ ] Helper: `execute`, `fetchone`, `fetchall`, JSON serialize
- [ ] Feature flag đọc `SEO_AEO_DB`
- [ ] Deprecate comment trên `ptt_seo/schema.py` — **freeze, no new DDL**

### Bước 3 — Module migration (3–5 ngày)

Migrate theo thứ tự dependency:

1. `client_settings`, `projects`, `initiatives`
2. `research` (keywords, questions)
3. `content`, `workflow`
4. `technical`, `connectors/gsc`, `automation`, `report`

Pattern mỗi module:

- PG implementation file hoặc branch trong module
- Giữ signature function; đổi connection type
- Unit test logic; integration test PG

### Bước 4 — Backfill (1 ngày)

- [ ] Script đọc SQLite `seo_*` → upsert PG
- [ ] Verify row counts per table per `customer_id`
- [ ] Log discrepancies

### Bước 5 — Dual-write pilot (2–3 ngày)

- [ ] `SEO_AEO_DB=dual` staging: write cả hai, read PG
- [ ] So sánh counts 24h
- [ ] Fix drift

### Bước 6 — Cutover production (1 ngày)

- [ ] Maintenance window ngắn (optional — upsert idempotent)
- [ ] Run backfill final
- [ ] Set `SEO_AEO_DB=pg`
- [ ] SQLite `seo_*` → read-only (app layer reject writes)

### Bước 7 — Cleanup (sau 2 tuần ổn định)

- [ ] Remove SQLite code path
- [ ] Drop SQLite `seo_*` tables (script + backup)
- [ ] Update tests bỏ in-memory SQLite schema cho integration

---

## Definition of Done (gate Phase 4)

- [ ] Production `SEO_AEO_DB=pg` ≥ 7 ngày không incident P1
- [ ] 1 client pilot UAT pass (hub, research, content, technical, reports)
- [ ] Backfill verified: 100% rows migrated hoặc documented exceptions
- [ ] Không PR mới thêm SQLite SEO schema (policy compliance)
- [ ] Worker job test ghi PG sync_runs thành công
- [ ] Runbook rollback tested trên staging

---

## Rollback

1. Set `SEO_AEO_DB=sqlite`
2. App reads/writes SQLite `seo_*` (data frozen tại thời điểm cutover)
3. PG data giữ làm backup — không drop
4. Post-mortem trước khi retry cutover

---

## Rủi ro

| Rủi ro | Giảm thiểu |
|--------|------------|
| SQL dialect khác (`?` vs `%s`, UPSERT) | Adapter layer tập trung |
| CRM join cross-DB | Giữ app-level `customer_id`; cache tên client nếu cần |
| Downtime | Idempotent backfill; dual-write pilot |
| Team vẫn code SQLite | Policy + PR checklist + block Phase 4 |

---

## Tests

```bash
# Local (cần Docker PG)
export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
export SEO_AEO_DB=pg
python3 -m unittest tests.test_seo_aeo_pg_cutover -v
python3 -m unittest tests.test_seo_aeo_phase1 tests.test_seo_aeo_phase2 tests.test_seo_aeo_phase3 -v
```

---

## Lịch sử

| Date | Change |
|------|--------|
| 2026-07-19 | Initial plan — gate before Phase 4 |
