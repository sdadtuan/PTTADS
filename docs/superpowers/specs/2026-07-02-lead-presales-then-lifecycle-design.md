# Design: Pre-sales trên Lead → KH + Lifecycle khi ký HĐ

**Ngày:** 2026-07-02  
**Trạng thái:** Chờ duyệt  
**Quyết định sản phẩm:** Hồ sơ `crm_customers` chỉ xuất hiện khi hợp đồng `status=active`. Trước đó mọi việc trên Lead.

---

## 1. Vấn đề

Luồng hiện tại:

- AI qualify tạo **draft lifecycle** sớm (gắn `lead_id`, chưa có KH).
- Convert KH thủ công (→ Case/KH), tách rời lifecycle.
- Service Delivery hiển thị deal pre-sales như lifecycle đầy đủ.
- `activate_lifecycle()` đã auto ✓ Lead/Consult/Proposal và nhảy **Onboard** — nhưng cần draft lifecycle + KH có sẵn.

Yêu cầu mới:

1. **Lead / Consult / Proposal** gắn trên **CRM Lead** (không phải Service Delivery).
2. **Chưa ký HĐ** → không có bản ghi Khách hàng.
3. **Ký HĐ** (`crm_contracts.status=active`) → tự động: Lead → KH + tạo Lifecycle **bắt đầu Onboard** (3 bước đầu coi như hoàn thành).
4. AM trên Lifecycle chỉ làm từ **bước 4 (Onboard)** trở đi.

---

## 2. Ba phương án

### A — Bảng pre-sales riêng (khuyến nghị)

| Thành phần | Mô tả |
|---|---|
| `crm_lead_presales` | 1 row/lead: `service_slug`, `stage` (lead\|consult\|proposal), metadata |
| `crm_lead_presales_tasks` | Task + form_data (copy pattern `crm_svc_tasks`, FK `presales_id`) |
| Intake | Giữ `crm_lead_intake_sessions` — chỉ `lead_id`, không `lifecycle_id` trong giai đoạn pre-sales |
| Ký HĐ | `promote_presales_to_lifecycle(lead_id, contract_id)` → convert KH, seed lifecycle, ✓ 3 stage, `stage=onboard`, `status=active` |

**Ưu:** Đúng nghĩa “chưa có Lifecycle”; ranh giới rõ.  
**Nhược:** Module mới; migrate UI Consult Brief / prefill sang lead presales.

### B — Lifecycle ẩn `status=presales`

Giữ `crm_service_lifecycle` từ sớm nhưng `status=presales`, không list trên Service Delivery; UI chỉ trên Lead.

**Ưu:** Tái dùng consult bridge, tasks, funnel.  
**Nhược:** Vẫn có row lifecycle trước KH — lệch wording “mới tạo Lifecycle”.

### C — Chỉ metadata trên `crm_leads`

Stage + JSON form trên lead; ký HĐ mới materialize lifecycle.

**Ưu:** Ít bảng.  
**Nhược:** Khó audit, khó tái dùng task engine / AI assist.

**Khuyến nghị: A** — khớp quyết địch “KH + Lifecycle chỉ sau HĐ”, vẫn tái dùng logic task/intake qua adapter mỏng.

---

## 3. Kiến trúc đề xuất (Phương án A)

### 3.1. Giai đoạn Pre-sales (trên Lead)

```
Lead (owner auto-assign)
  └─ crm_lead_presales (stage: lead → consult → proposal)
       ├─ tasks (seed từ crm_svc_workflow_steps[slug][stage])
       ├─ intake sessions (lead_id only)
       └─ consult gate / BANT (logic từ crm_svc_consult_bridge, đổi FK presales)
```

**UI `/crm/leads`:**

- Panel **“Pre-sales dịch vụ”** (3 tab: Lead | Consult | Proposal) — embed task cards + Intake + Consult Brief tương tự workflow, route `/crm/leads/<id>/presales` hoặc drawer.
- **Tắt** tạo draft lifecycle từ `crm_ai_qualify.py` (feature flag `PTT_PRESALES_ON_LEAD=1`).

**Không hiển thị** deal pre-sales trên kanban Service Delivery (hoặc filter `status=presales` cũ nếu còn data legacy).

### 3.2. Hợp đồng

Thêm cột:

```sql
ALTER TABLE crm_contracts ADD COLUMN lead_id INTEGER REFERENCES crm_leads(id);
```

- Tạo HĐ từ Lead (hoặc Proposal pre-sales): `lead_id` bắt buộc, `customer_id` **NULL** khi draft.
- `service_slug` lấy từ `crm_lead_presales.service_slug`.

### 3.3. Kích hoạt khi ký HĐ

Hook trong `api_crm_update_contract` khi `status` → `active`:

```python
def on_contract_signed(conn, contract_id) -> dict:
    # 1. convert_lead_to_crm(lead_id) → customer_id
    # 2. UPDATE contract SET customer_id = ...
    # 3. promote_presales_to_lifecycle(lead_id, customer_id, contract_id)
    #    - create crm_service_lifecycle (active, stage=onboard)
    #    - copy tasks/form_data/intake refs từ presales → lifecycle tasks
    #    - complete_all_stage_tasks(lead, consult, proposal)
    #    - ghi lifecycle_events: presales hoàn tất → onboard
    # 4. UPDATE lead status → won / post_sale (sync care pipeline)
    # 5. (Tuỳ chọn) đóng presales row status=converted
```

Tái sử dụng logic sẵn có trong `activate_lifecycle()` (✓ 3 stage + onboard) nhưng **tạo lifecycle mới** thay vì tìm draft theo `customer_id`.

### 3.4. Giai đoạn Delivery (Lifecycle)

- AM mở `/crm/service-delivery/<lifecycle_id>` — **stage hiện tại = Onboard**.
- Tab Lead/Consult/Proposal: read-only (đã ✓) hoặc ẩn; focus Onboard → Deliver → Handover → Retain.
- KPI / funnel: pre-sales metrics vẫn đo trên lead + presales; delivery metrics trên lifecycle.

---

## 4. Mapping dữ liệu

| Nguồn (pre-sales) | Đích (lifecycle) |
|---|---|
| `crm_lead_presales_tasks.form_data` | `crm_svc_tasks.form_data` (theo stage) |
| Intake sessions | Giữ nguyên, gán thêm `lifecycle_id` sau promote |
| `assigned_am` (từ lead owner) | `crm_service_lifecycle.assigned_am` |
| Proposal draft (nếu có) | `crm_proposals` gắn `customer_id` + `lifecycle_id` sau promote |

---

## 5. Migration & tương thích

| Legacy | Xử lý |
|---|---|
| Draft lifecycle cũ (`status=draft`, có `lead_id`) | Script backfill → presales hoặc giữ read-only; không tạo mới |
| Lifecycle đã có `customer_id` | Không đổi |
| Convert thủ công → Case/KH | Ẩn nút hoặc chuyển thành “Xem preview KH” — KH thật chỉ khi HĐ |
| Proposal cần `customer_id` | Trước HĐ: proposal “draft trên lead”; sau promote: copy sang `crm_proposals` |

Feature flag: `PTT_PRESALES_ON_LEAD=1` (default off trên VPS cho đến khi pilot xong).

---

## 6. Kiểm thử

- Lead presales: seed tasks, advance lead→consult→proposal, gate BANT/No-Go.
- HĐ draft với `lead_id`, `customer_id` null.
- Ký HĐ → 1 KH, 1 lifecycle active stage=onboard, 3 stage tasks done.
- Service Delivery không list presales; list lifecycle sau ký.
- Regression: BĐS `won` + RE product vẫn qua `complete_deal_closure` (merge hook).

---

## 7. Phạm vi triển khai (ước lượng)

| Phase | Nội dung | Effort |
|---|---|---|
| P1 | Schema presales + tắt AI draft lifecycle + API presales | 2–3 ngày |
| P2 | UI 3 tab trên CRM Lead + intake/consult bridge adapter | 3–4 ngày |
| P3 | Contract `lead_id` + `on_contract_signed` promote | 2 ngày |
| P4 | Migration legacy + docs + pilot 1 dịch vụ | 1–2 ngày |

**Tổng ~8–11 ngày** (1 dev).

---

## 8. Rủi ro

- Proposal AI trước HĐ không có `customer_id` — cần mode draft trên lead.
- Funnel KPI hiện filter theo lifecycle — cập nhật query presales + lifecycle.
- AM quen workflow cũ — training + song song feature flag.

---

## 9. Chưa làm (YAGNI)

- Tự động tạo HĐ từ Proposal (giữ thủ công).
- Gán SP trên lifecycle (phase riêng).
- KPI target theo từng bước trên Lead UI.
