# CRM Service Delivery — Tài liệu nội bộ

Tài liệu vận hành **Service Lifecycle** (7 giai đoạn), **Lead Intake**, và **Pre-sales trên Lead** (Phương án A) cho team AM / Sales / CSKH PTT.

| Tài liệu | Mục đích |
|----------|----------|
| **[HDSD trên hệ thống](/crm/hdsd)** | Đọc & tải file `.md` / **Excel** / ZIP toàn bộ tài liệu |
| **[Test Case Excel](/crm/test-cases/download.xlsx)** | Bộ TC CRM đầy đủ cột + sơ đồ + hướng dẫn chụp hình ([hướng dẫn tester](./bo-test-case-huong-dan-tester.md)) |
| **[Hướng dẫn đầy đủ Lead → Retain](./huong-dan-day-du-lead-den-cham-soc-khach-hang.md)** | Toàn bộ công đoạn, sơ đồ, cách sử dụng từng bước, KPI, test case |
| **[Nguồn lead & Setup (FB / Zalo / Webform)](./huong-dan-nguon-lead-va-setup.md)** | Chu trình ingest, cấu hình `.env`, Meta/Zalo webhook, landing form, API |

## Truy cập CRM

| Mục | URL (sau khi đăng nhập admin) |
|-----|-------------------------------|
| **Quản lý Lead (pre-sales)** | `/crm/leads` |
| Service Delivery Kanban | `/crm/service-delivery` |
| Workflow chi tiết (per KH) | `/crm/service-delivery/<lifecycle_id>` |
| Lead Intake (web) | `/crm/intake?lead_id=…` hoặc `?lifecycle_id=…` (legacy) |
| Hợp đồng / Marketing Hub | `/crm/hub` |
| Form Lead in/PDF | `/crm/forms/lead-intake/<file>.html` |

Port mặc định: xem `restart_flask.sh` / biến `PORT` (thường `5050` hoặc `5006`).

**Feature flag pre-sales trên Lead:** `PTT_PRESALES_ON_LEAD=1` trong `.env` (mặc định **tắt** trên VPS cho đến khi pilot xong).

---

## Pre-sales trên Lead — Phương án A (P1–P4)

Luồng mới: **Lead → Pre-sales (Lead/Tư vấn/Báo giá) → HĐ draft → Ký HĐ → KH + Lifecycle Onboard**.

| Giai đoạn | Ở đâu | Ghi chú |
|-----------|--------|---------|
| Pre-sales | `/crm/leads` — panel 3 tab | Không tạo KH; không hiện trên kanban Delivery |
| Intake BANT | `/crm/intake?lead_id=` | Gắn lead, không cần lifecycle |
| HĐ draft | `/crm/hub` hoặc nút trên Lead | KH **placeholder** `[Lead #id] Chưa ký — …` |
| Ký HĐ | Hub → status **Active** | `convert_lead_to_crm` + `promote_presales_to_lifecycle` |
| Delivery | `/crm/service-delivery/<id>` | Bắt đầu **Onboard**; 3 bước đầu đã ✓ |

**Tài liệu:**

| Tài liệu | Mục đích |
|----------|----------|
| [Spec kỹ thuật A](../superpowers/specs/2026-07-02-lead-presales-then-lifecycle-design.md) | Kiến trúc, API, migration |
| [Kế hoạch triển khai](../superpowers/plans/2026-07-02-lead-presales-then-lifecycle.md) | Phase P1–P4 |
| [Checklist pilot](./presales-on-lead-pilot-checklist.md) | Bật flag, backfill, smoke test |

**Module code:** `crm_lead_presales.py`, `crm_lead_presales_bridge.py`, `crm_lead_presales_contract.py`, `crm_lead_presales_legacy.py`

**Backfill lifecycle draft cũ → presales:**

```bash
cd PTTADS
python3 scripts/backfill_draft_lifecycle_to_presales.py --dry-run
python3 scripts/backfill_draft_lifecycle_to_presales.py --limit 100
```

Khi flag **bật**: AI qualify **không** tạo draft lifecycle; nút **→ Case/KH** trên Lead bị ẩn; kanban Delivery **không** list lifecycle `draft`.

---

## Giai đoạn Tư vấn (Consult) — Phase C0

| Tài liệu | Mục đích |
|----------|----------|
| [Consult Stage PPT](../Consult_Stage_Service_Delivery.pptx) | Slide đào tạo AM (~45 phút) |
| [SOP AM — Consult](../runbooks/consult-stage-am-sop.md) | Quy trình hàng ngày |
| [Hướng dẫn facilitator](../runbooks/consult-stage-training-guide.md) | Kịch bản buổi training |
| [Phụ lục task 12 DV](../runbooks/consult-stage-service-tasks.md) | Form fields Consult từng dịch vụ |
| [BANT sign-off](../runbooks/consult-stage-bant-signoff.md) | Director phê duyệt ngưỡng Go/Nurture |
| [Checklist hoàn thành C0](../runbooks/consult-stage-c0-completion.md) | Trạng thái triển khai Phase C0 |

**Spec kỹ thuật:** [2026-06-30-consult-stage-system-design.md](../specs/2026-06-30-consult-stage-system-design.md)  
**Kế hoạch code C1–C6:** [2026-06-30-consult-stage-system.md](../superpowers/plans/2026-06-30-consult-stage-system.md)

**C1 (done):** `crm_svc_consult_bridge.get_consult_brief`, API consult-brief, panel Consult Brief trên workflow (stage Consult). Gate Brief dùng BANT **24/18** đến Director sign-off §6. **Trên Lead (flag bật):** `crm_lead_presales_bridge.get_presales_brief` + panel tab Tư vấn tại `/crm/leads`.

**C2 (done):** `get_crm_field_map` (12 slug), `prefill_consult_task` — auto khi advance Lead→Consult; POST `/api/crm/service-lifecycle/<id>/consult-prefill`; nút **Prefill form Consult** trên panel Brief.

**C3 (done):** `validate_consult_advance` (gate No-Go/Nurture/BANT, Director override); `on_intake_completed` (auto ✓ Lead khi in_person+GO+BANT≥24, ghi chú No-Go); banner + confirm trên workflow; PATCH lifecycle validate trước Consult.

**C4 (done):** `build_ai_context_for_consult` merge Consult Brief vào AI assist; template `consult_analysis` có BANT/Intake/Lead qualify; POST `/api/crm/svc-tasks/<id>/ai-assist` tự enrich khi stage=consult.

**C5 (done):** `get_customer_context` đọc task Consult (+ Intake brief); `run_proposal_ai` inject audit Consult; nút **Tạo Proposal từ Consult** + prefill `/crm/proposals` (service slug, ghi chú).

**C6 (done):** Funnel cohort trên Service Delivery (L3); `get_lifecycle_funnel_progress` + panel **Funnel deal này** trên workflow; API `GET .../funnel-progress`; deep-link cohort từ workflow.

### Tạo lại tài liệu

```bash
cd PTTADS
python3 scripts/generate_consult_stage_pptx.py
python3 scripts/generate_consult_runbook_appendix.py
```

---

## Lead Intake (giai đoạn Lead)

| Tài liệu | Link |
|----------|------|
| Form HTML 13 file | [docs/forms/lead-intake/README.md](../forms/lead-intake/README.md) |
| Checklist Lead PPT | [Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx](../Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx) |
| Spec Lead Intake | [2026-06-30-lead-intake-system-design.md](../specs/2026-06-30-lead-intake-system-design.md) |
| **Lead KPI + chi phí pre-contract** | [2026-06-30-lead-kpi-precontract-cost-design.md](../specs/2026-06-30-lead-kpi-precontract-cost-design.md) |
| Kế hoạch L1–L4 | [2026-06-30-lead-kpi-precontract-cost.md](../superpowers/plans/2026-06-30-lead-kpi-precontract-cost.md) |

**L1 (done):** Chi phí pre-sales — migration `cost_phase`, API, panel workflow.

**L2 (done):** `get_am_lead_metrics`, API lead-metrics, section Lead trên `/crm/staff-kpi`.

**L3 (done):** `get_funnel_stats`, API funnel-stats, widget Funnel Pre-sales trên `/crm/service-delivery`; intake stats `by_am`.

**L4 (done):** AI scan Lead (`run_ai_lead_kpi_scan`, role `am_lead`); cap pre-sales per lifecycle + banner workflow.

---

## Spec hệ thống liên quan

- [Lead pre-sales → Lifecycle on contract](../superpowers/specs/2026-07-02-lead-presales-then-lifecycle-design.md)
- [Service Workflow Engine](../specs/2026-06-22-service-workflow-engine-design.md)
- [SPEC hệ thống PTT](../SPEC_HE_THONG_PTT.md)
