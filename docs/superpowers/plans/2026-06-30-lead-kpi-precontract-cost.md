# Plan: Lead KPI + Chi phí Pre-contract + Funnel Stats

> **Mục tiêu:** Đo effort và chi phí **pre-sales** (Lead → Consult → Proposal) theo AM; funnel dashboard team; **không** nhầm với doanh thu KH.

**Design spec:** [2026-06-30-lead-kpi-precontract-cost-design.md](../../specs/2026-06-30-lead-kpi-precontract-cost-design.md)

**Tiền đề:** P0 `owner_id` → `assigned_am` ✅

**Gộp Consult C6:** Funnel stats triển khai tại **L3** trong module `crm_svc_presales.py` — Consult C6 chỉ wire UI nếu chưa xong.

---

## Phase L1 — Chi phí pre-sales (3 ngày)

### Task L1.1: Schema migration

**Files:**
- Modify: `crm_svc_finance.py` — `ensure_schema` thêm `cost_phase`, `lifecycle_stage`
- Modify: `tests/test_crm_svc_finance.py`

**Steps:**
- [x] Migration idempotent ALTER TABLE
- [x] `create_expense(..., cost_phase='presales', lifecycle_stage='lead')`
- [x] `get_summary()` — `delivery_expenses` vs `presales_expenses` tách key; margin chỉ dùng delivery
- [x] Test: presales expense không làm giảm `profit` post-HĐ

### Task L1.2: Presales summary API

**Files:**
- Create: `crm_svc_presales.py` — `get_presales_cost_summary()` only
- Modify: `app.py` — route GET presales-summary
- Create: `tests/test_crm_svc_presales.py` (skeleton)

**Steps:**
- [x] API trả total + by_category
- [x] Auto-set `cost_phase`/`lifecycle_stage` từ lifecycle khi POST expense nếu client không gửi

### Task L1.3: UI panel Pre-sales

**Files:**
- Modify: `templates/crm_service_workflow.html`

**Steps:**
- [x] Panel chỉ khi draft + stage lead/consult/proposal
- [x] Form thêm expense + list 8 dòng gần nhất
- [x] Copy UX từ finance expenses section

---

## Phase L2 — KPI Lead AM (3 ngày)

### Task L2.1: `get_am_lead_metrics`

**Files:**
- Modify: `crm_svc_presales.py` — full metrics §5.1 spec
- Modify: `tests/test_crm_svc_presales.py`

**Steps:**
- [x] `lead_intake_completed`
- [x] `lead_phone_within_48h_pct`
- [x] `lead_go_decisions`
- [x] `lead_to_consult_pct`
- [x] `presales_cost_vnd`
- [x] `lead_avg_phone_minutes` (session có started_at + completed_at)

### Task L2.2: Staff KPI UI

**Files:**
- Modify: `templates/crm_staff_kpi.html`
- Modify: `app.py` — `crm_staff_kpi_page` pass `am_lead_metrics`

**Steps:**
- [x] Section 「AM — Lead (Pre-sales)」
- [x] Target inputs: `lead_intake_completed`, `lead_phone_within_48h_pct`, `lead_to_consult_pct`, `presales_cost_vnd`
- [x] Reuse `setTarget()` với metric_key mới

### Task L2.3: API route

**Files:**
- Modify: `app.py`

**Steps:**
- [x] `GET /api/crm/staff-kpi/<staff_id>/lead-metrics?year=&month=`

---

## Phase L3 — Funnel stats (3 ngày)

> Thay thế / gộp **Consult Phase C6** funnel dashboard.

### Task L3.1: `get_funnel_stats`

**Files:**
- Modify: `crm_svc_presales.py`
- Modify: `tests/test_crm_svc_presales.py`

**Steps:**
- [x] Cohort theo `lifecycle.created_at` trong kỳ
- [x] Filter `am_id`, `service_slug`
- [x] Ratios §6.1 + presales cost per go/won
- [x] `in_person_before_consult_pct` (Go leads)

### Task L3.2: Service Delivery widget

**Files:**
- Modify: `templates/crm_service_delivery.html`
- Modify: `app.py` — page context + `GET /api/crm/service-lifecycle/funnel-stats`

**Steps:**
- [x] Funnel bar visual (CSS, không chart lib mới)
- [x] Filter AM dropdown
- [x] Giữ widget Intake coverage hiện tại; bổ sung funnel bên dưới

### Task L3.3: Mở rộng intake stats

**Files:**
- Modify: `crm_lead_intake.py` — `get_intake_stats(by_am=False)` optional breakdown

**Steps:**
- [x] `by_am: [{ staff_id, name, intake_completed, avg_bant }]`
- [x] API `GET /api/crm/intake/stats?am_id=`

---

## Phase L4 — AI & cảnh báo (2 ngày, optional)

### Task L4.1: AI lead KPI scan

**Files:**
- Modify: `crm_svc_kpi.py` — `_AM_LEAD_PROMPT`, `run_ai_lead_kpi_scan()`
- Modify: `templates/crm_staff_kpi.html`

**Steps:**
- [x] Prompt so sánh actual vs target Lead
- [x] Gợi ý giảm `presales_cost_per_go`

### Task L4.2: Cap alert

**Steps:**
- [x] Config `presales_cost_cap_vnd` per lifecycle (optional meta JSON lifecycle.notes hoặc bảng config sau)
- [x] Banner workflow khi presales > cap

---

## Verification

```bash
cd PTTADS
python3 -m unittest tests.test_crm_svc_presales tests.test_crm_svc_finance tests.test_crm_svc_kpi -v
```

Manual:
1. Lifecycle draft stage Lead + assigned AM → ghi chi phí `dien_thoai`
2. Panel pre-sales hiện tổng; Finance margin HĐ vẫn 0
3. `/crm/staff-kpi` section Lead hiện actual
4. `/crm/service-delivery` funnel bar cập nhật sau chuyển Consult

---

## Mapping Consult program

| Consult phase | Lead KPI phase |
|---------------|----------------|
| C6 funnel dashboard | **L3** (implement here) |
| C0–C5 | Không block L1–L2 |

---

*PTT CRM · Lead Pre-sales KPI Program*
