# Chính sách lưu trữ SEO/AEO — PostgreSQL-only (từ 2026-07-19)

> **Trạng thái:** **ACTIVE — bắt buộc cho mọi PR/feature mới**  
> **Phạm vi:** Bounded context `ptt_seo/`, blueprint `seo_aeo`, worker jobs SEO/AEO, DDL mới  
> **Liên quan:** [`2026-07-19-seo-aeo-architecture.md`](2026-07-19-seo-aeo-architecture.md) · [`2026-07-17-sqlite-pg-migration.md`](2026-07-17-sqlite-pg-migration.md) · [`../superpowers/plans/2026-07-19-seo-aeo-phase3.5-pg-cutover.md`](../superpowers/plans/2026-07-19-seo-aeo-phase3.5-pg-cutover.md)

---

## 1. Tóm tắt (1 câu)

**Từ ngày 2026-07-19, team không được thêm bảng, cột, feature hay job mới ghi dữ liệu SEO/AEO vào SQLite — mọi phát triển mới và cutover dùng PostgreSQL schema `seo_aeo`.**

---

## 2. Bối cảnh

| Giai đoạn | Thực tế code | Spec gốc |
|-----------|--------------|----------|
| Phase 0–3 (đã ship) | `ptt_seo/*` + `ptt_seo/schema.py` trên **SQLite** (`ptt.db`) | Target: PG schema `seo_aeo` |
| Phase 3.5 (bắt buộc trước Phase 4) | Wire PG + backfill + feature flag cutover | — |
| Phase 4+ | Feature mới **chỉ PG** | GSC OAuth, AEO v2, worker sync |

Phase 1–3 là **technical debt có kiểm soát** — giữ để UAT và backfill, **không mở rộng**.

---

## 3. Quy tắc bắt buộc

### 3.1. Cấm (không merge PR vi phạm)

| Hành vi | Lý do |
|---------|-------|
| Thêm bảng `seo_*` mới trong SQLite | Volume + worker sync cần PG |
| Thêm cột / index mới vào bảng `seo_*` SQLite (trừ hotfix P0 đã approve) | Trì hoãn cutover |
| Feature mới ghi keywords, content, issues, GSC stats, alerts vào SQLite | Vi phạm ADR-SEO-006 |
| Job handler mới (`ptt_jobs/handlers/*`) ghi SEO domain vào SQLite | Worker đã dùng PG |
| Test/integration mới assume SQLite là store lâu dài | Gây lock-in |

### 3.2. Cho phép (tạm thời)

| Hành vi | Ghi chú |
|---------|---------|
| **Đọc** SQLite CRM master: `crm_customers`, `crm_service_lifecycle`, `crm_staff` | Bridge qua `customer_id` — không FK cross-DB |
| **Đọc** AEO legacy: `crm_aeo_queries`, `crm_aeo_scans` | Migrate Phase 4; chỉ read hoặc bugfix |
| Bugfix trên code SQLite hiện có **không** thêm schema | Backport tối thiểu |
| Dual-write tạm PG + SQLite **chỉ** trong ticket Phase 3.5 cutover | Có ngày kết thúc rõ |

### 3.3. Bắt buộc cho mọi feature mới (Phase 4+)

1. DDL trong [`deploy/sql/seo_aeo_pg_schema.sql`](../../deploy/sql/seo_aeo_pg_schema.sql) — **không** `ptt_seo/schema.py` SQLite
2. Data access qua `ptt_seo/db.py` → `ptt_jobs.db.pg_connection()` (sẽ tạo Phase 3.5)
3. Worker jobs enqueue PG `job_queue`; handler ghi `seo_aeo.*`
4. Test: PG fixture (Docker `ptt_agency`) hoặc mock — in-memory SQLite **chỉ** cho unit test logic thuần, không cho schema mới
5. PR checklist: tick mục **“Không thêm SQLite SEO schema”**

---

## 4. Phân tách dual-database (chấp nhận được)

```
┌─────────────────────────────────────────────────────────┐
│  Flask UI / API (seo_aeo blueprint)                     │
├──────────────────────────┬──────────────────────────────┤
│  READ (tạm)              │  WRITE (mọi feature mới)     │
│  SQLite CRM master       │  PostgreSQL seo_aeo.*        │
│  customer_id bridge      │  job_queue, sync_runs, …     │
└──────────────────────────┴──────────────────────────────┘
```

**Không** coi dual-DB là lý do tiếp tục ghi SEO vào SQLite.

---

## 5. Lộ trình cutover

| Phase | Mục tiêu | SQLite SEO |
|-------|----------|------------|
| **3** ✅ | MVP Technical, GSC CSV, Reports, Automation | Legacy store (freeze) |
| **3.5** 🔴 **Gate bắt buộc** | PG wiring, backfill, `SEO_AEO_DB=pg`, UAT 1 client | Read-only sau cutover |
| **4** | GSC/GA4 OAuth, AEO v2, worker sync | Deprecate tables |
| **4 end** | Drop SQLite `seo_*` tables (migration script) | **Removed** |

**Phase 4 feature work bị block** cho đến khi Phase 3.5 gate pass (xem plan Phase 3.5).

---

## 6. Exception process

Chỉ Tech Lead + người duyệt migration matrix có thể approve exception SQLite:

1. Ghi rõ lý do P0 (production down)
2. Ticket có ngày sunset ≤ 2 tuần
3. Follow-up ticket Phase 3.5 bắt buộc

---

## 7. PR review checklist

- [ ] Không có `CREATE TABLE seo_*` mới trong SQLite migrations
- [ ] Không có `ALTER TABLE seo_*` SQLite (trừ approved hotfix)
- [ ] DDL mới nằm trong `deploy/sql/seo_aeo_pg_schema.sql`
- [ ] Module mới dùng PG connection helper, không `deps.get_connection()` cho SEO writes
- [ ] Worker handler (nếu có) ghi PG
- [ ] Doc/plan cập nhật nếu thêm entity mới

---

## 8. Liên kết artifact

| Artifact | Vai trò |
|----------|---------|
| [`deploy/sql/seo_aeo_pg_schema.sql`](../../deploy/sql/seo_aeo_pg_schema.sql) | Source of truth DDL |
| [`2026-07-19-seo-aeo-architecture.md`](2026-07-19-seo-aeo-architecture.md) | ADR-SEO-006 |
| [`2026-07-19-seo-aeo-phase3.5-pg-cutover.md`](../superpowers/plans/2026-07-19-seo-aeo-phase3.5-pg-cutover.md) | Implementation plan |
| [`2026-07-17-sqlite-pg-migration.md`](2026-07-17-sqlite-pg-migration.md) | Platform-wide matrix (SEO = order 3.5) |

---

## Lịch sử

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-19 | SQLite freeze; Phase 3.5 gate; team policy active |
