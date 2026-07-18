# Consult Stage System — Kế hoạch triển khai

> **Mục tiêu:** Vận hành giai đoạn **Tư vấn (Consult)** trong Service Lifecycle — brief Lead, prefill, gate funnel, AI, Proposal bridge.

**Design spec:** [2026-06-30-consult-stage-system-design.md](../../specs/2026-06-30-consult-stage-system-design.md)

**Tech stack:** Flask 3, SQLite, Jinja2, Vanilla JS, Anthropic Haiku

---

## Global constraints

- Không phá `validate_stage_advance` sequential hiện có
- Session master = Lead Intake; Consult task = operational audit record
- Prefill chỉ fill key **trống** (trừ `overwrite=True` admin tool)
- Tests: `unittest` + in-memory SQLite
- Auth pattern giống Lead Intake / Service Workflow

---

## Phase C0 — SOP & đào tạo (2 ngày)

**Goal:** AM hiểu khác biệt Lead vs Consult trước khi code.

### Task C0.1: PowerPoint đào tạo

**Files:**
- Create: `scripts/generate_consult_stage_pptx.py`
- Output: `docs/Consult_Stage_Service_Delivery.pptx`

- [x] Chạy script; review với Sales lead
- [x] Upload link nội bộ trong README CRM (`docs/crm/README.md`)

### Task C0.2: SOP 1 trang

**Files:**
- Create: `docs/runbooks/consult-stage-am-sop.md`
- Create: `docs/runbooks/consult-stage-training-guide.md`
- Create: `docs/runbooks/consult-stage-bant-signoff.md`
- Create: `docs/runbooks/consult-stage-c0-completion.md`
- Create: `scripts/generate_consult_runbook_appendix.py` → `consult-stage-service-tasks.md`

Nội dung: checklist hàng ngày AM (từ spec §11).

- [ ] DIR sign-off ngưỡng BANT Go/Nurture/No-Go (`consult-stage-bant-signoff.md`)
- [ ] Buổi training AM (facilitator guide)
- [ ] Sales lead review PPT

---

## Phase C1 — Consult Brief (4 ngày)

**Goal:** AM thấy toàn bộ output Lead khi vào Consult.

### Task C1.1: Module bridge — read path

**Files:**
- Create: `crm_svc_consult_bridge.py`
- Create: `tests/test_crm_svc_consult_bridge.py`

**Functions (phase 1):**
```python
def get_consult_brief(conn, lifecycle_id) -> dict
def _load_lead_task(conn, lifecycle_id) -> dict | None
def _load_intake_sessions(conn, lifecycle_id) -> list[dict]
def _build_recommended_actions(brief) -> list[str]
```

- [x] Test: lifecycle có intake completed → brief có bant/decision
- [x] Test: lifecycle không intake → recommended_actions gợi ý mở Intake

### Task C1.2: API + workflow template

**Files:**
- Modify: `app.py` — route GET consult-brief; pass `consult_brief` to workflow page
- Modify: `templates/crm_service_workflow.html` — panel HTML + CSS

- [x] Panel chỉ render khi `lifecycle.stage == 'consult'`
- [x] Link mở Intake in_person nếu thiếu session completed mode=in_person

---

## Phase C2 — Prefill Consult (3 ngày)

**Goal:** Form Consult có sẵn data từ Lead.

### Task C2.1: Field map

**Files:**
- Modify: `crm_lead_intake_definitions.py` — `get_crm_field_map(slug) -> dict[str, str]`
- Modify: `crm_svc_consult_bridge.py` — `get_lead_to_consult_field_map`, `prefill_consult_task`

- [x] Map tối thiểu 12 slug (smoke: SEO, FB Ads, LP)
- [x] Test: prefill không overwrite existing values

### Task C2.2: Hook advance + lazy prefill

**Files:**
- Modify: `crm_service_lifecycle.py` — gọi `prefill_consult_task` sau `advance_stage(..., 'consult')`
- Modify: `app.py` — POST `/consult-prefill` for manual retry

- [x] Chuyển Lead→Consult → consult task có current_status filled

---

## Phase C3 — Gate & automation (4 ngày)

**Goal:** Funnel có kiểm soát; giảm thao tác thủ công.

### Task C3.1: validate_consult_advance

**Files:**
- Modify: `crm_svc_consult_bridge.py`
- Modify: `app.py` — PATCH lifecycle gọi validate trước advance to consult

- [x] no_go → 400 unless `override_reason` + role check
- [x] nurture → 200 with warning in JSON (frontend confirm)

### Task C3.2: on_intake_completed

**Files:**
- Modify: `crm_lead_intake.py` — `complete_session` gọi `on_intake_completed`
- Modify: `crm_svc_consult_bridge.py`

- [x] in_person + go + BANT≥24 → lead task is_done=1
- [x] phone + go → activity next_action "Hẹn PHẦN B"

### Task C3.3: UI banners

**Files:**
- Modify: `templates/crm_service_workflow.html`
- Modify: inline JS — confirm dialog nurture/no_go override

- [x] Ẩn Lead Intake banner khi stage != lead
- [x] Banner "Sẵn sàng chuyển Tư vấn" khi lead done + go

---

## Phase C4 — AI context (3 ngày)

**Goal:** AI Consult dùng full brief.

### Task C4.1: build_ai_context_for_consult

**Files:**
- Modify: `crm_svc_consult_bridge.py`
- Modify: `app.py` — `api_svc_task_ai_assist` merge context when task.stage=consult

- [x] Test mock: AI prompt input contains intake excerpt

### Task C4.2: Template tweak (optional)

**Files:**
- Modify: `crm_svc_workflow_steps.py` — extend `consult_analysis` template placeholders

- [x] Placeholders BANT/decision/intake_summary/lead_form_json/red_flags

---

## Phase C5 — Proposal bridge (4 ngày)

**Goal:** Báo giá kế thừa audit Consult.

### Task C5.1: get_customer_context

**Files:**
- Modify: `crm_proposal.py`
- Modify: `tests/test_crm_proposal.py`

- [x] Context có consult.form_data + ai_output

### Task C5.2: UI shortcut

**Files:**
- Modify: `templates/crm_service_workflow.html` — nút "Tạo Proposal" khi consult done

- [x] Nút **Tạo Proposal từ Consult** + prefill trang `/crm/proposals`

---

## Phase C6 — KPI funnel (2 ngày → gộp Lead program L3)

**Goal:** Dashboard funnel Go→Consult→Proposal.

**Triển khai tại:** [2026-06-30-lead-kpi-precontract-cost.md](./2026-06-30-lead-kpi-precontract-cost.md) **Phase L3** — module `crm_svc_presales.get_funnel_stats()`. Consult C6 chỉ wire UI nếu L3 chưa xong.

### Task C6.1: Wire funnel widget (sau L3)

**Files:**
- Modify: `app.py` — truyền stats vào `crm_service_delivery.html` (gọi `crm_svc_presales`)

- [x] Widget Go→Consult, Consult→Proposal (L3 trên `/crm/service-delivery`)
- [x] Mini-widget funnel per lifecycle trên workflow + API `funnel-progress`
- [x] Test SQL counts với fixture data (`test_crm_svc_presales_funnel.py` + consult bridge)

---

## Thứ tự ưu tiên

```
C0 (SOP/PPT) → C1 (Brief) → C2 (Prefill) → C3 (Gate)
                                    ↓
              C4 (AI) → C5 (Proposal) → C6 (KPI)
```

| Tuần | Deliverable |
|------|-------------|
| 1 | C0 + C1 |
| 2 | C2 + C3 |
| 3 | C4 + C5 |
| 4 | C6 + UAT go-live |

---

## Checklist go-live

- [ ] Training 45p với PPT Consult Stage
- [ ] 2 lifecycle pilot: SEO + Facebook Ads end-to-end
- [ ] Director approve gate rules no_go/nurture
- [ ] Monitor 2 tuần: consult prefill rate, time consult→proposal

---

## Files tổng hợp

| File | Phase |
|------|-------|
| `docs/specs/2026-06-30-consult-stage-system-design.md` | ✅ |
| `docs/Consult_Stage_Service_Delivery.pptx` | C0 |
| `scripts/generate_consult_stage_pptx.py` | C0 |
| `crm_svc_consult_bridge.py` | C1–C6 |
| `tests/test_crm_svc_consult_bridge.py` | C1+ |
| `docs/runbooks/consult-stage-am-sop.md` | C0 |
